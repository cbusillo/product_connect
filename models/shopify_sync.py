import logging
import threading
import traceback
from contextlib import contextmanager
from time import sleep
from typing import Generator, Union

from babel.dates import format_timedelta
from httpx import RequestError
from odoo import api, models, fields
from psycopg2 import OperationalError, InterfaceError
from psycopg2.errors import TransactionRollbackError
from pydantic import BaseModel

from ..utils.shopify_helpers import (
    SyncMode,
    ShopifyApiError,
    OdooDataError,
    format_datetime_for_shopify,
    DEFAULT_DATETIME,
    ShopifySyncRunFailed,
)

_logger = logging.getLogger(__name__)


class ShopifySync(models.TransientModel):
    _name = "shopify.sync"
    _description = "Shopify Sync"
    _inherit = ["mail.activity.mixin", "mail.thread", "notification.manager.mixin"]
    _transient_max_hours = 24 * 7
    _transient_max_count = 1000

    MAX_RETRY_ATTEMPTS = 5
    RETRYABLE_ERRORS = (
        ShopifyApiError,
        OdooDataError,
        TransactionRollbackError,
        OperationalError,
        InterfaceError,
        RequestError,
    )

    LOCK_ID = 87945012
    IMPORT_EXPORT_CRON_TIME = 60 * 60
    CRON_IDLE_TIMEOUT_THRESHOLD_SECONDS = 60  # TODO: increase in prod

    start_time = fields.Datetime()
    start_time_human = fields.Char(compute="_compute_start_time_human", string="Started")
    end_time = fields.Datetime()
    end_time_human = fields.Char(compute="_compute_end_time_human", string="Ended")
    run_time = fields.Float(compute="_compute_run_time", string="Run Time (seconds)")
    run_time_human = fields.Char(compute="_compute_run_time", string="Run Time")

    mode = fields.Selection(SyncMode.choices(), required=True, index=True)
    odoo_products_to_sync = fields.Many2many("product.product")
    shopify_product_id_to_sync = fields.Char(string="Shopify Product ID")
    datetime_to_sync = fields.Datetime()
    updated_count = fields.Integer()
    total_count = fields.Integer()
    progress_percent = fields.Float(string="Progress %", compute="_compute_progress_percent", store=True)
    retry_attempts = fields.Integer(default=0)

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

    @api.model
    def fields_get(self, allfields: list[str] | None = None, attributes: list[str] | None = None) -> dict[str, dict]:
        resource = super().fields_get(allfields, attributes)
        if (
            (mode := resource.get("mode"))
            and (selection := mode.get("selection"))
            and not self.env["ir.config_parameter"].sudo().get_param("shopify.test_store")
        ):
            mode["selection"] = [select for select in selection if select[0] != "reset_shopify"]

        return resource

    @api.model_create_multi
    def create(self, vals_list: Union[list["odoo.values.shopify_sync"], "odoo.values.shopify_sync"]) -> "odoo.model.shopify_sync":
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        self._fail_stale_runs()
        self.env.cr.flush()
        vals_to_create: list["odoo.values.shopify_sync"] = []
        for vals in vals_list:
            domain = [
                ("mode", "=", vals["mode"]),
                ("state", "in", ["running", "queued"]),
                ("shopify_product_id_to_sync", "=", vals.get("shopify_product_id_to_sync")),
                ("datetime_to_sync", "=", vals.get("datetime_to_sync")),
            ]
            potential_duplicates = self.search(domain)

            if vals["mode"] == SyncMode.EXPORT_BATCH:
                command = vals.get("odoo_products_to_sync") or []
                product_ids: list[int] = []
                if command and command[0][0] == 6:
                    product_ids = sorted(command[0][2])

                product_ids_copy = tuple(product_ids)

                potential_duplicates = potential_duplicates.filtered(
                    lambda sync, ids=product_ids_copy: tuple(sorted(sync.odoo_products_to_sync.ids)) == ids
                )

            if potential_duplicates:
                _logger.debug(f"Duplicate Shopify sync found: {vals['mode']}")
                continue

            vals_to_create.append(vals)

        if not vals_to_create:
            return self.browse()

        syncs = super().create(vals_to_create)
        syncs.state = "queued"
        return syncs

    def unlink(self) -> models.BaseModel:
        self.env["mail.activity"].search([("res_id", "in", self.ids)]).unlink()
        self.env["mail.message"].search([("res_id", "in", self.ids)]).unlink()

        return super().unlink()

    @api.depends("updated_count", "total_count")
    def _compute_progress_percent(self) -> None:
        for record in self:
            record.progress_percent = (record.updated_count / record.total_count) * 100 if record.total_count else 0.0

    def _compute_start_time_human(self) -> None:
        for record in self:
            if record.start_time:
                record.start_time_human = format_timedelta(fields.Datetime.now() - record.start_time, locale="en_US")
                record.start_time_human += " ago"
            else:
                record.start_time_human = "-"

    def _compute_end_time_human(self) -> None:
        for record in self:
            if record.end_time:
                record.end_time_human = format_timedelta(fields.Datetime.now() - record.end_time, locale="en_US")
                record.end_time_human += " ago"
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

    # ------------------------------------------------------------------

    def _fail_stale_runs(self, threshold_seconds: int = 0) -> None:
        if not threshold_seconds:
            threshold_seconds = self.CRON_IDLE_TIMEOUT_THRESHOLD_SECONDS

        cutoff = fields.Datetime.subtract(fields.Datetime.now(), seconds=threshold_seconds)
        stale_runs = self.search([("state", "=", "running"), ("write_date", "<", cutoff)])
        if not stale_runs:
            return

        class StaleRunTimeout(Exception):
            pass

        for run in stale_runs:
            if run.retry_attempts < run.MAX_RETRY_ATTEMPTS:
                run.write(
                    {
                        "state": "queued",
                        "retry_attempts": run.retry_attempts + 1,
                        "error_message": f"Auto-retry after {threshold_seconds}s inactivity",
                        "start_time": False,
                        "end_time": False,
                    }
                )
                _logger.warning(f"Re-queued stale sync {run.id} (run {run.retry_attempts + 1}/{run.MAX_RETRY_ATTEMPTS})")
            else:
                vals = run._prepare_failure_vals(StaleRunTimeout(f"No activity for {threshold_seconds}s"))
                vals["end_time"] = run.write_date
                run.write(vals)
        self.env.cr.commit()

    @api.model
    def _cron_dispatch_next(self) -> None:
        self._fail_stale_runs()

        while True:
            next_sync = None  # silence linters / ensure defined
            with self.env.cr.savepoint():
                self.env.cr.execute("SELECT pg_try_advisory_lock(%s)", [self.LOCK_ID])
                if not self.env.cr.fetchone()[0]:
                    _logger.debug("Another worker already running; skipping.")
                    return

                if self.search([("state", "=", "running")], limit=1):
                    self.env.cr.execute("SELECT pg_advisory_unlock(%s)", [self.LOCK_ID])
                    _logger.debug("Sync already running; skipping.")
                    return

                next_sync = self.search(
                    [("state", "=", "queued")],
                    order="retry_attempts desc, id asc",
                    limit=1,
                )
                if next_sync:
                    next_sync.write(
                        {
                            "state": "running",
                            "start_time": fields.Datetime.now(),
                        }
                    )
                self.env.cr.execute("SELECT pg_advisory_unlock(%s)", [self.LOCK_ID])

            if not next_sync:
                _logger.debug("No queued syncs found; exiting dispatcher.")
                break

            try:
                next_sync._execute_mode()
            except (ShopifyApiError, OdooDataError, ShopifySyncRunFailed):
                self.env.cr.commit()
                continue
            except Exception:
                self.env.cr.commit()
                raise

        if self.search([("state", "in", ["running", "queued"])], limit=1):
            _logger.debug("Another sync is running; exiting dispatcher.")
            return

        now = fields.Datetime.now()
        cutoff = fields.Datetime.subtract(now, seconds=self.IMPORT_EXPORT_CRON_TIME)

        def _is_healthy(mode: SyncMode) -> bool:
            in_flight = self.search_count([("mode", "=", mode.value), ("state", "in", ["queued", "running"])])
            recent = self.search_count([("mode", "=", mode.value), ("state", "=", "success"), ("start_time", ">=", cutoff)])
            return bool(in_flight or recent)

        healthy_import = _is_healthy(SyncMode.IMPORT_THEN_EXPORT)
        healthy_export = _is_healthy(SyncMode.EXPORT_CHANGED)

        if not (healthy_import and healthy_export):
            self.create({"mode": SyncMode.IMPORT_THEN_EXPORT.value})

    def run_async(self) -> None:
        _logger.debug(f"Running async sync for {self}")

        def run_in_thread() -> None:
            with self.env.registry.cursor() as cr:
                thread_env = self.env(cr)
                sync_jobs = thread_env["shopify.sync"].sudo().browse(self.ids)
                for sync_job in sync_jobs:
                    sync_job._cron_dispatch_next()

        threading.Thread(target=run_in_thread, daemon=True).start()

    def create_and_run_async(
        self, vals_list: Union[list["odoo.values.shopify_sync"], "odoo.values.shopify_sync"]
    ) -> "odoo.model.shopify_sync":
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        sync_jobs = self.create(vals_list)
        self.env.cr.commit()
        if sync_jobs:
            sync_jobs.run_async()
        return sync_jobs

    def duplicate_and_run_async(self) -> "odoo.model.shopify_sync":
        new_syncs = self.duplicate()
        self.env.cr.commit()
        new_syncs.run_async()
        return new_syncs

    def duplicate(self) -> "odoo.model.shopify_sync":
        new_syncs = self.env["shopify.sync"]
        for sync in self:
            new_sync = sync.create(
                {
                    "mode": sync.mode,
                    "datetime_to_sync": sync.datetime_to_sync,
                    "odoo_products_to_sync": sync.odoo_products_to_sync,
                    "shopify_product_id_to_sync": sync.shopify_product_id_to_sync,
                }
            )
            new_syncs |= new_sync
        return new_syncs

    @api.model
    def _execute_mode(self) -> None:
        if self.mode not in {m.value for m in SyncMode}:
            raise ValueError(f"Unknown sync mode: {self.mode!r}")
        runner = getattr(self, f"_run_{self.mode}", None)

        if not callable(runner):
            raise ValueError(f"No handler for mode: {self.mode!r}")
        with self._run_guard():
            runner()

    def _prepare_failure_vals(self, error: Exception) -> "odoo.values.shopify_sync":
        tb = traceback.format_exc()
        vals: "odoo.values.shopify_sync" = {
            "end_time": fields.Datetime.now(),
            "error_message": str(error),
            "error_exception": error.__class__.__name__,
            "error_traceback": tb,
        }

        should_retry = self.retry_attempts < self.MAX_RETRY_ATTEMPTS and isinstance(error, self.RETRYABLE_ERRORS)
        if should_retry:
            sleep(self.retry_attempts)
            vals["state"] = "queued"
            vals["retry_attempts"] = self.retry_attempts + 1
            _logger.warning(
                f"Scheduling retry {vals['retry_attempts']}/{self.MAX_RETRY_ATTEMPTS} for Shopify sync {self.id} ({self.mode})",
            )
        else:
            vals["state"] = "failed"

            self.notify_channel_on_error(
                f"Shopify sync failed",
                vals["error_message"],
                self.error_odoo_record,
                self.error_shopify_record or self.error_shopify_input,
            )

        return vals

    def _mark_failed(self, error: Exception) -> None:
        truncate = lambda s, l=100000: s if len(s) <= l else s[:l] + f"...[{len(s)-l} more]"
        vals = self._prepare_failure_vals(error)

        if hasattr(error, "odoo_record") and isinstance(error.odoo_record, models.Model):
            vals["error_odoo_record"] = error.odoo_record

        if hasattr(error, "shopify_record") and isinstance(error.shopify_record, BaseModel):
            vals["error_shopify_record"] = error.shopify_record.model_dump(exclude_none=True, mode="json")

        if hasattr(error, "shopify_input") and isinstance(error.shopify_input, BaseModel):
            vals["error_shopify_input"] = error.shopify_input.model_dump(exclude_none=True, mode="json")

        if hasattr(error, "errors"):
            raw_errors = error.errors() if callable(error.errors) else error.errors
            try:
                errors = list(raw_errors)
            except TypeError:
                errors = [raw_errors]
            combined = "\n".join(map(str, errors))
            vals["error_shopify_record"] = truncate(f"{vals.get('error_shopify_record', '')}\n{combined}".strip())

        self.write(vals)
        self.env.cr.commit()
        _logger.error(f"Shopify sync failed:\n{vals['error_traceback']}")

    @contextmanager
    def _run_guard(self) -> Generator[None, None, None]:
        self.write({"state": "running"})
        self.env.cr.commit()
        try:
            yield
            self.state = "success"
            if (
                self.mode in (SyncMode.IMPORT_CHANGED.value, SyncMode.IMPORT_THEN_EXPORT.value, SyncMode.IMPORT_ALL.value)
                and self.last_import_start_time
            ):
                self.env["ir.config_parameter"].set_param(
                    "shopify.last_import_time", format_datetime_for_shopify(self.last_import_start_time)
                )
            self.env.cr.commit()
        except Exception as error:
            self._mark_failed(error)
            self.env.cr.commit()
            raise ShopifySyncRunFailed()
        finally:
            self.end_time = fields.Datetime.now()
            self.env.cr.commit()

    @property
    def completed_str(self) -> str:
        return f"{self.updated_count} of {self.total_count} product(s)"

    def _run_reset_shopify(self) -> None:
        from ..services.shopify_product_deleter import ProductDeleter

        deleter = ProductDeleter(self.env, self)
        deleter.delete_all_products()

        products = self.env["product.product"].search([])
        products.shopify_product_id = False
        products.shopify_next_export = False
        products.shopify_last_exported_at = False
        products.shopify_next_export_images = False
        products.shopify_next_export_quantity_change_amount = 0
        products.shopify_created_at = False
        products.shopify_variant_id = False
        products.shopify_condition_id = False
        products.shopify_ebay_category_id = False

        self.total_count = len(products)
        self.env.cr.commit()

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

        self.env["shopify.sync"].create({"mode": SyncMode.EXPORT_CHANGED.value, "state": "queued"})

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

    def _run_import_since_date(self) -> None:
        _logger.info("Importing products from Shopify since a specific date")
        from ..services.shopify_product_importer import ProductImporter

        importer = ProductImporter(self.env, self)
        if not self.datetime_to_sync:
            raise ValueError("Datetime to sync is not set.")
        filter_query = f'updated_at:>"{format_datetime_for_shopify(self.datetime_to_sync)}"'
        importer.import_products_from_query(filter_query)

    def _run_export_since_date(self) -> None:
        _logger.info("Exporting products to Shopify since a specific date")
        from ..services.shopify_product_exporter import ProductExporter

        if not self.datetime_to_sync:
            raise ValueError("Datetime to sync is not set.")

        exporter = ProductExporter(self.env, self)
        exporter.export_products_since_datetime(self.datetime_to_sync)
