import logging
from datetime import datetime

from odoo import fields
from odoo.api import Environment

from odoo.addons.product_connect.services.shopify_client import (
    OptionSetInput,
    VariantOptionValueInput,
    LocalizableContentType,
    ProductSetIdentifiers,
)
from .shopify_client import (
    InventoryItemMeasurementInput,
    ProductSetProductSetProductResourcePublicationsV2,
    ProductSetProductSetProductResourcePublicationsV2EdgesNodePublication,
    ProductSetProductSetProduct,
    GraphQLClientGraphQLMultiError,
)
from .shopify_client.enums import ProductStatus, MetafieldValueType, WeightUnit
from .shopify_client.input_types import (
    ProductSetInput,
    ProductVariantSetInput,
    ProductSetInventoryInput,
    FileSetInput,
    PublicationInput,
    WeightInput,
    InventoryItemInput,
    MetafieldInput,
    OptionValueSetInput,
)
from .shopify_service import ShopifyService
from ..utils.shopify_helpers import (
    ShopifyApiError,
    OdooDataError,
    format_shopify_gid_from_id,
    format_sku_bin_for_shopify,
    parse_shopify_id_from_gid,
)

_logger = logging.getLogger(__name__)

PUBLICATION_CHANNELS = {
    "online_store": "19453116480",
    "pos": "42683596853",
    "google": "88268636213",
    "shop": "99113467957",
}

COMMIT_AFTER = 100


class ProductExporter:
    def __init__(self, env: Environment):
        self.env = env
        self.shopify_service = ShopifyService(env)
        self.odoo_base_url = env["ir.config_parameter"].sudo().get_param("web.base.url")

    def export_products_since_last_export(self) -> tuple[int, int]:
        _logger.info("Exporting products since last export")
        odoo_products = self._find_products_to_export()
        if not odoo_products:
            _logger.info("No products to export")
            return 0, 0
        return self.export_products(odoo_products)

    def _find_products_to_export(self) -> "odoo.model.product_product":
        odoo_products = self.env["product.product"].search(
            [
                ("sale_ok", "=", True),
                ("is_ready_for_sale", "=", True),
                ("website_description", "!=", False),
                ("website_description", "!=", ""),
            ]
        )

        odoo_products = odoo_products.filtered(
            lambda p: p.shopify_next_export is True
            or (
                p.write_date > (p.shopify_last_exported or datetime.min)
                or p.product_tmpl_id.write_date > (p.shopify_last_exported or datetime.min)
            )
        )
        return odoo_products

    def export_products(self, odoo_products: "odoo.model.product_product") -> tuple[int, int]:
        exported_products = 0
        total_count = len(odoo_products)
        for odoo_product in odoo_products:
            _logger.debug(f"Exporting product {exported_products} of {total_count}: {odoo_product.id} {odoo_product.name}")
            try:
                with self.env.cr.savepoint():
                    self.export_product(odoo_product)
            except (ShopifyApiError, OdooDataError, ValueError, GraphQLClientGraphQLMultiError) as error:
                _logger.error(f"Error exporting product {odoo_product.id}: {error}")
                self.env.cr.commit()
                raise error
            exported_products += 1
            if exported_products and exported_products % COMMIT_AFTER == 0:
                _logger.debug(f"Committing after {exported_products} products")
                self.env.cr.commit()

        return exported_products, total_count

    def export_product(self, odoo_product: "odoo.model.product_product") -> None:
        client = self.shopify_service.client
        shopify_product_set_input = self._map_odoo_product_to_shopify_product_set_input(odoo_product)

        shopify_product_gid = (
            format_shopify_gid_from_id("Product", odoo_product.shopify_product_id) if odoo_product.shopify_product_id else None
        )
        if shopify_product_gid:
            identifier = ProductSetIdentifiers(id=shopify_product_gid)
        else:
            identifier = None

        try:
            shopify_response = client.product_set(shopify_product_set_input, identifier)
        except (ValueError, GraphQLClientGraphQLMultiError) as error:
            _logger.debug(
                f"Error exporting product {shopify_product_set_input} with GID {shopify_product_gid} to Shopify: {error}"
            )
            raise OdooDataError(f"Error exporting product {odoo_product.id} to Shopify: {error}")

        shopify_product = shopify_response.product_set.product
        if not shopify_product:
            raise ShopifyApiError("Shopify product not found in the response")

        if not self.is_published_on_all_channels(shopify_product.resource_publications_v_2):
            self._publish_product(shopify_product_gid)
        self._update_odoo_product(odoo_product, shopify_product)

    @staticmethod
    def _update_odoo_product(odoo_product: "odoo.model.product_product", shopify_product: ProductSetProductSetProduct) -> None:
        if not shopify_product:
            raise ShopifyApiError("Shopify product not found in the response")

        metafields_by_key = {edge.node.key: edge.node for edge in shopify_product.metafields.edges}
        ebay_category_id_metafield = metafields_by_key.get("ebay_category_id")
        condition_metafield = metafields_by_key.get("condition")
        _logger.debug(
            f"Updating product {odoo_product.id} with Shopify product {shopify_product.id} and metafields {metafields_by_key}"
        )

        odoo_product.write(
            {
                "shopify_product_id": parse_shopify_id_from_gid(shopify_product.id),
                "shopify_variant_id": parse_shopify_id_from_gid(shopify_product.variants.edges[0].node.id),
                "shopify_condition_id": parse_shopify_id_from_gid(condition_metafield.id) if condition_metafield else None,
                "shopify_ebay_category_id": (
                    parse_shopify_id_from_gid(ebay_category_id_metafield.id) if ebay_category_id_metafield else None
                ),
                "shopify_last_exported": fields.Datetime.now(),
                "shopify_next_export": False,
            }
        )

    def is_published_on_all_channels(self, publication_channels: ProductSetProductSetProductResourcePublicationsV2) -> bool:
        for publication_channel in publication_channels.edges:
            if not self.is_published_on_channel(publication_channel.node.publication):
                return False
        return True

    @staticmethod
    def is_published_on_channel(
        publication_channel: ProductSetProductSetProductResourcePublicationsV2EdgesNodePublication,
    ) -> bool:
        return parse_shopify_id_from_gid(publication_channel.id) in PUBLICATION_CHANNELS.values()

    def _publish_product(self, shopify_product_gid: str) -> None:
        client = self.shopify_service.client
        publication_input = [
            PublicationInput(
                publicationId=format_shopify_gid_from_id("Publication", publication_id),
                publishDate=True,
            )
            for publication_id in PUBLICATION_CHANNELS.values()
        ]
        publication_input[0].publication_id = PUBLICATION_CHANNELS["online_store"]
        client.update_publications(shopify_product_gid, publication_input)

    def _map_odoo_product_to_shopify_product_set_input(self, odoo_product: "odoo.model.product_product") -> ProductSetInput:
        shopify_inventory_set_input = []
        shopify_file_set_input = []
        if not odoo_product.shopify_product_id:
            shopify_file_set_input = [
                FileSetInput(
                    alt=odoo_product.name,
                    originalSource=self.odoo_base_url + "/web/image/product.image/" + str(odoo_image.id) + "/image_1920",
                )
                for odoo_image in odoo_product.images.sorted("name")
            ]

            shopify_inventory_set_input = [
                ProductSetInventoryInput(
                    locationId=self.shopify_service.first_location_gid,
                    quantity=int(odoo_product.qty_available),
                    name="available",
                )
            ]

        shopify_inventory_item_measurement_input = InventoryItemMeasurementInput(
            weight=WeightInput(
                value=odoo_product.weight,
                unit=WeightUnit.POUNDS,
            ),
        )

        shopify_inventory_item_input = InventoryItemInput(
            cost=odoo_product.standard_price,
            measurement=shopify_inventory_item_measurement_input,
        )

        shopify_variant_set_input = ProductVariantSetInput(
            id=(
                format_shopify_gid_from_id("ProductVariant", odoo_product.shopify_variant_id)
                if odoo_product.shopify_variant_id
                else None
            ),
            price=odoo_product.list_price,
            sku=format_sku_bin_for_shopify(odoo_product.default_code, odoo_product.bin),
            barcode=odoo_product.mpn,
            inventoryItem=shopify_inventory_item_input,
            inventoryQuantities=shopify_inventory_set_input,
            optionValues=[VariantOptionValueInput(optionName="Title", name="Default Title")],
        )

        shopify_product_set_input = ProductSetInput(
            title=odoo_product.name,
            descriptionHtml=odoo_product.website_description,
            vendor=odoo_product.manufacturer.name if odoo_product.manufacturer else None,
            productType=odoo_product.part_type.name if odoo_product.part_type else None,
            status=ProductStatus.ACTIVE if odoo_product.qty_available > 0 else ProductStatus.DRAFT,
            variants=[shopify_variant_set_input],
            files=shopify_file_set_input,
            metafields=[],
            productOptions=[OptionSetInput(name="Title", values=[OptionValueSetInput(name="Default Title")])],
        )

        if odoo_product.condition.code:
            shopify_product_set_input.metafields += [
                MetafieldInput(
                    id=(
                        format_shopify_gid_from_id("Metafield", odoo_product.shopify_condition_id)
                        if odoo_product.shopify_condition_id
                        else None
                    ),
                    namespace="custom",
                    key="condition",
                    value=odoo_product.condition.code,
                    type=LocalizableContentType.SINGLE_LINE_TEXT_FIELD.lower(),
                )
            ]

        if odoo_product.shopify_ebay_category_id:
            shopify_product_set_input.metafields += [
                MetafieldInput(
                    id=(
                        format_shopify_gid_from_id("Metafield", odoo_product.shopify_ebay_category_id)
                        if odoo_product.shopify_ebay_category_id
                        else None
                    ),
                    namespace="custom",
                    key="ebay_category_id",
                    value=str(odoo_product.part_type.ebay_category_id),
                    type=MetafieldValueType.INTEGER,
                )
            ]

        return shopify_product_set_input
