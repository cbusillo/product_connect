import logging
import traceback

from babel.dates import format_timedelta
from contextlib import contextmanager
from typing import Generator

from odoo import api, models, fields

from odoo.addons.product_connect.utils.shopify_helpers import (
    ShopifyApiError,
    OdooDataError,
    format_datetime_for_shopify,
    DEFAULT_DATETIME,
)

_logger = logging.getLogger(__name__)


class ShopifySync(models.TransientModel):
    _name = "shopify.sync"
    _description = "Shopify Sync"
    _inherit = ["notification.manager.mixin", "mail.activity.mixin", "mail.thread"]
    _order = "start_time DESC"

    start_time = fields.Datetime(default=fields.Datetime.now, required=True)
    start_time_human = fields.Char(compute="_compute_start_time_human", string="Started")
    end_time = fields.Datetime()
    end_time_human = fields.Char(compute="_compute_end_time_human", string="Ended")
    run_time = fields.Float(compute="_compute_run_time")
    run_time_human = fields.Char(compute="_compute_run_time", string="Run Time")

    LOCK_ID = 87945012

    mode = fields.Selection(
        [
            ("import_then_export", "Import Then Export"),
            ("import_changed", "Import Changed"),
            ("export_changed", "Export Changed"),
            ("import_all", "Import All"),
            ("export_all", "Export All"),
            ("import_since", "Import Since Date"),
            ("export_since", "Export Since Date"),
            ("import_one", "Import One"),
            ("export_batch", "Export batch"),
            ("reset_shopify", "Reset Shopify IDs"),
        ],
        required=True,
        index=True,
    )
    odoo_products_to_sync = fields.Many2many("product.product")
    shopify_product_id_to_sync = fields.Integer()
    datetime_to_sync = fields.Datetime()
    updated_count = fields.Integer()
    total_count = fields.Integer()
    progress_percent = fields.Float(
        string="Progress %",
        compute="_compute_progress_percent",
        store=True,
        aggregator="avg",
    )

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("running", "Running"),
            ("success", "Success"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
        index=True,
    )

    user = fields.Many2one("res.users", default=lambda self: self.env.user)
    last_import_start_time = fields.Datetime()

    error_message = fields.Text()
    error_traceback = fields.Text()
    error_exception = fields.Text()
    error_odoo_record = fields.Many2one("product.product")
    error_shopify_record = fields.Json()
    error_shopify_input = fields.Json()

    @api.model_create_multi
    def create(self, vals_list: list["odoo.values.shopify_sync"]) -> "odoo.model.shopify_sync":
        self._fail_stale_runs()
        syncs = super().create(vals_list)
        syncs.state = "queued"
        return syncs

    @api.depends("updated_count", "total_count")
    def _compute_progress_percent(self) -> None:
        for record in self:
            record.progress_percent = (record.updated_count / record.total_count) * 100 if record.total_count else 0.0

    def _compute_start_time_human(self) -> None:
        for record in self:
            if record.start_time:
                record.start_time_human = format_timedelta(fields.Datetime.now() - record.start_time, locale="en_US")
            else:
                record.start_time_human = "-"

    def _compute_end_time_human(self) -> None:
        for record in self:
            if record.end_time:
                record.end_time_human = format_timedelta(fields.Datetime.now() - record.end_time, locale="en_US")
            else:
                record.end_time_human = "-"

    def _compute_run_time(self) -> None:
        for record in self:
            if record.end_time and record.start_time:
                time_delta = record.end_time - record.start_time
                record.run_time = time_delta.total_seconds()
                record.run_time_human = format_timedelta(time_delta, locale="en_US")
            else:
                record.run_time = 0.0
                record.run_time_human = "-"

    def _fail_stale_runs(self, threshold_seconds: int = 60) -> None:
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), seconds=threshold_seconds)
        stale_runs = self.search(
            [
                ("state", "=", "running"),
                ("write_date", "<", cutoff),
            ]
        )
        if not stale_runs:
            return

        mark_failed_vals: "odoo.values.shopify_sync" = {
            "state": "failed",
            "error_message": f"Automatically marked failed - no activity for {threshold_seconds} seconds",
            "end_time": fields.Datetime.now(),
        }
        stale_runs.write(mark_failed_vals)
        self.env.cr.commit()

    @api.model
    def _cron_dispatch_next(self) -> None:
        self._fail_stale_runs()

        self.env.cr.execute("SELECT pg_try_advisory_lock(%s)", [self.LOCK_ID])
        if not self.env.cr.fetchone()[0]:
            _logger.debug("Another cron worker is already draining the queue.")
            return

        if self.search([("state", "=", "running")], limit=1):
            _logger.debug("Another sync is already running, skipping dispatch.")
            return
        try:
            while True:
                self.env.cr.commit()
                next_sync = self.search([("state", "=", "queued")], order="id asc", limit=1)
                if not next_sync:
                    break

                try:
                    next_sync._execute_mode()
                except (ShopifyApiError, OdooDataError):
                    self.env.cr.commit()
                    continue
        finally:
            self.env.cr.execute("SELECT pg_advisory_unlock(%s)", [self.LOCK_ID])
            self.env.cr.commit()

        now = fields.Datetime.now()
        last_import_then_export = self.search(
            [("mode", "=", "import_then_export"), ("state", "!=", "failed")], order="start_time DESC", limit=1
        )
        last_export_changed = self.search(
            [("mode", "=", "export_changed"), ("state", "!=", "failed")], order="start_time DESC", limit=1
        )
        if (
            not last_import_then_export
            or (now - last_import_then_export.start_time).total_seconds() >= 3600
            or not last_export_changed
            or (now - last_export_changed.start_time).total_seconds() >= 3600
        ):
            self.create({"mode": "import_then_export"})

    @api.model
    def _execute_mode(self) -> None:
        dispatch = {
            "import_then_export": self._run_import_then_export,
            "import_changed": self._run_import_changed,
            "export_changed": self._run_export_changed,
            "import_since": self._run_import_since,
            "export_since": self._run_export_since,
            "import_all": self._run_import_all,
            "export_all": self._run_export_all,
            "import_one": self._run_import_one,
            "export_batch": self._run_export_batch,
            "reset_shopify": self._run_reset_shopify,
        }

        runner = dispatch.get(self.mode)

        if not runner:
            raise ValueError(f"Invalid sync mode: {self.mode}")

        with self._run_guard():
            runner()

    def _mark_failed(self, error: Exception) -> None:
        tb = traceback.format_exc()
        vals: "odoo.values.shopify_sync" = {
            "state": "failed",
            "end_time": fields.Datetime.now(),
            "error_message": str(error),
            "error_exception": error.__class__.__name__,
            "error_traceback": tb,
        }

        if isinstance(error, (ShopifyApiError, OdooDataError)):
            vals["error_odoo_record"] = error.odoo_record

        if isinstance(error, ShopifyApiError):
            if error.shopify_input:
                vals["error_shopify_input"] = error.shopify_input.model_dump(exclude_none=True, mode="json")
            if error.shopify_record:
                vals["error_shopify_record"] = error.shopify_record.model_dump(exclude_none=True, mode="json")

        self.sudo().write(vals)
        self.env.cr.commit()
        _logger.error("Shopify sync failed: %s", tb)

    @contextmanager
    def _run_guard(self) -> Generator[None, None, None]:
        self.sudo().write({"state": "running"})
        self.env.cr.commit()
        try:
            yield
            self.state = "success"
            if self.mode in ("import_changed", "import_then_export", "import_all"):
                self.env["ir.config_parameter"].sudo().set_param(
                    "shopify.last_import_time", format_datetime_for_shopify(self.last_import_start_time)
                )
        except Exception as error:
            self._mark_failed(error)
            raise
        finally:
            self.end_time = fields.Datetime.now()

    @property
    def completed_str(self) -> str:
        return f"{self.updated_count} of {self.total_count} product(s)"

    @property
    def is_success(self) -> bool:
        return self.updated_count == self.total_count

    def _run_reset_shopify(self) -> None:
        products = self.env["product.product"].search([])
        self.total_count = len(products)
        self.env.cr.commit()
        products.shopify_product_id = False
        products.shopify_next_export = False
        products.shopify_last_exported_at = False
        products.shopify_next_export_images = False
        products.shopify_next_export_quantity_change_amount = 0
        products.shopify_created_at = False
        products.shopify_variant_id = False
        products.shopify_condition_id = False
        products.shopify_ebay_category_id = False
        self.updated_count = self.total_count

    def _run_import_all(self) -> None:
        _logger.info("Importing all products from Shopify")
        from ..services.shopify_product_importer import ProductImporter

        self.last_import_start_time = fields.Datetime.now()
        importer = ProductImporter(self.env, self)
        importer.import_products_from_query()

    def _run_export_all(self) -> None:
        _logger.info("Exporting all products to Shopify")
        from ..services.shopify_product_exporter import ProductExporter

        exporter = ProductExporter(self.env, self)
        exporter.export_products_since_datetime(DEFAULT_DATETIME)

    def _run_import_then_export(self) -> None:
        self._run_import_changed()

        self.env["shopify.sync"].create(
            {
                "mode": "export_changed",
                "state": "queued",
            }
        )

    def _run_import_changed(self) -> None:
        _logger.info("Importing changed products from Shopify")
        from ..services.shopify_product_importer import ProductImporter

        self.last_import_start_time = fields.Datetime.now()
        importer = ProductImporter(self.env, self)
        importer.import_products_since_last_import()

    def _run_export_changed(self) -> None:
        _logger.info("Exporting changed products to Shopify")
        from ..services.shopify_product_exporter import ProductExporter

        exporter = ProductExporter(self.env, self)
        exporter.export_products_since_last_export()

    def _run_import_one(self) -> None:
        _logger.info("Importing one product from Shopify")
        from ..services.shopify_product_importer import ProductImporter

        importer = ProductImporter(self.env, self)
        importer.import_product_by_id(self.shopify_product_id_to_sync)

    def _run_export_batch(self) -> None:
        _logger.info("Exporting batch of products to Shopify")
        from ..services.shopify_product_exporter import ProductExporter

        exporter = ProductExporter(self.env, self)
        exporter.export_products(self.odoo_products_to_sync)

    def _run_import_since(self) -> None:
        _logger.info("Importing products from Shopify since a specific date")
        from ..services.shopify_product_importer import ProductImporter

        importer = ProductImporter(self.env, self)
        if not self.datetime_to_sync:
            raise ValueError("Datetime to sync is not set.")
        filter_query = f'updated_at:>"{format_datetime_for_shopify(self.datetime_to_sync)}"'
        importer.import_products_from_query(filter_query)

    def _run_export_since(self) -> None:
        _logger.info("Exporting products to Shopify since a specific date")
        from ..services.shopify_product_exporter import ProductExporter

        if not self.datetime_to_sync:
            raise ValueError("Datetime to sync is not set.")

        exporter = ProductExporter(self.env, self)
        exporter.export_products_since_datetime(self.datetime_to_sync)
