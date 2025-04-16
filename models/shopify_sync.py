import logging

from odoo import api, models

from odoo.addons.product_connect.utils.shopify_helpers import OdooDataError, ShopifyApiError

_logger = logging.getLogger(__name__)


class ShopifySync(models.AbstractModel):
    _name = "shopify.sync"
    _description = "Shopify Sync"
    _inherit = ["notification.manager.mixin"]

    @api.model
    def sync_with_shopify(self) -> None:
        _logger.info("Starting Shopify sync")

        try:
            import_results = self.import_changed_products_from_shopify()
            _logger.info(f"Import results: {import_results}")

            export_results = self.export_changed_products_to_shopify()
            _logger.info(f"Export results: {export_results}")
        except (OdooDataError, ShopifyApiError, ValueError, IndexError) as error:
            self.notify_channel_on_error(
                "Import or export with Shopify failed",
                "",
                record=error.record if hasattr(error, "record") else None,
                error=error,
            )
            raise error

        self._notify_sync_results(import_results, export_results)

    @api.model
    def import_changed_products_from_shopify(self) -> tuple[int, int]:
        _logger.info("Importing products from Shopify")
        from ..services.shopify_product_importer import ProductImporter

        importer = ProductImporter(self.env)
        return importer.import_products_since_last_import()

    @api.model
    def export_changed_products_to_shopify(self) -> tuple[int, int]:
        _logger.info("Exporting products to Shopify")
        from ..services.shopify_product_exporter import ProductExporter

        exporter = ProductExporter(self.env)
        return exporter.export_products_since_last_export()

    @api.model
    def import_product_from_shopify_by_id(self, shopify_product_id: str) -> None:
        _logger.info("Importing product from Shopify with ID: %s", shopify_product_id)
        from ..services.shopify_product_importer import ProductImporter

        importer = ProductImporter(self.env)
        importer.import_product_by_id(shopify_product_id)

    @api.model
    def export_product_to_shopify_by_id(self, product_id: int) -> None:
        _logger.info("Exporting product to Shopify with ID: %s", product_id)
        self.export_product_to_shopify(self.env["product.product"].browse(product_id))

    @api.model
    def export_product_to_shopify(self, product: "odoo.model.product_product") -> None:
        _logger.info("Exporting product to Shopify: %s", product.name)
        from ..services.shopify_product_exporter import ProductExporter

        exporter = ProductExporter(self.env)
        exporter.export_product(product)

    def _notify_sync_results(self, import_results: tuple[int, int], export_results: tuple[int, int]) -> None:
        _logger.info("Notifying sync results")
        if not import_results and export_results:
            return

        message = "Shopify Sync completed successfully"
        if import_results:
            updated_count, total_count = import_results
            message += f"\nImported {updated_count} out of {total_count} products from Shopify."
        if export_results:
            exported_count, total_count = export_results
            message += f"\nExported {exported_count} out of {total_count} products to Shopify."

        self.notify_channel("Shopify Sync Results", message, "shopify_sync")
