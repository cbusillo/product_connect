import logging

import httpx
from ariadne_codegen.client_generators.dependencies.exceptions import GraphQLClientGraphQLMultiError
from odoo.api import Environment

from odoo.addons.product_connect.utils.shopify_helpers import ShopifyApiError
from .shopify_client import ProductDeleteInput
from .shopify_service import ShopifyService
from ..utils.shopify_helpers import SHOPIFY_PAGE_SIZE

_logger = logging.getLogger(__name__)


class ProductDeleter:
    def __init__(self, env: Environment, sync_record: "odoo.model.shopify_sync") -> None:
        self.env = env
        self.service = ShopifyService(env)
        self.sync_record = sync_record

    def delete_all_products(self) -> None:
        product_ids_to_delete = self.get_all_product_ids_from_shopify()
        for product_id_to_delete in product_ids_to_delete:
            product_delete_input = ProductDeleteInput(id=product_id_to_delete)
            try:
                self.service.client.delete_product(input=product_delete_input)
            except (GraphQLClientGraphQLMultiError, httpx.HTTPError) as error:
                exception = ShopifyApiError("Failed to delete Shopify product", shopify_input=product_delete_input)
                _logger.error(exception)
                raise exception from error

            self.sync_record.updated_count += 1
            if self.sync_record.updated_count % (SHOPIFY_PAGE_SIZE // 5) == 0:
                self.env.cr.commit()
                _logger.info(f"Deleted {self.sync_record.updated_count} products so far.")

    def get_all_product_ids_from_shopify(self) -> list[str]:
        client = self.service.client
        cursor = None
        has_next_page = True
        all_product_ids = []

        while has_next_page:
            try:
                products_page = client.get_product_ids(cursor=cursor, limit=SHOPIFY_PAGE_SIZE)
            except (GraphQLClientGraphQLMultiError, httpx.HTTPError) as error:
                exception = ShopifyApiError("Failed to fetch product IDs from Shopify")
                _logger.error(exception)
                raise exception from error

            products = products_page.nodes
            product_ids = [product.id for product in products]
            all_product_ids.extend(product_ids)
            self.sync_record.total_count += len(product_ids)

            cursor = products_page.page_info.end_cursor
            has_next_page = products_page.page_info.has_next_page
            self.env.cr.commit()
            _logger.info(f"Fetched {len(all_product_ids)} product IDs.")

        return all_product_ids
