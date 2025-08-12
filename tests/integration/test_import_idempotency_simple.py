"""Simple integration tests for timestamp tracking in sync flow

These tests verify that the import process correctly tracks timestamps
to avoid re-importing the same data.
"""

from datetime import timezone
from typing import Any
from ..common_imports import tagged, datetime, timedelta, patch, MagicMock, INTEGRATION_TAGS
from ..fixtures.base import IntegrationTestCase
from ..fixtures.shopify_responses import (
    create_shopify_order_response,
    create_shopify_customer_response,
    create_shopify_order_line_item_response,
)
from ...services.shopify.gql import OrderFields
from ...services.shopify.sync.importers.order_importer import OrderImporter
from ...services.shopify.helpers import last_import_config_key, format_datetime_for_shopify


@tagged(*INTEGRATION_TAGS)
class TestImportIdempotencySimple(IntegrationTestCase):
    """Simple integration tests for timestamp tracking"""

    def setUp(self) -> None:
        super().setUp()
        self._setup_import_idempotency_test()

        # Clear any existing timestamp parameters
        self.env["ir.config_parameter"].search([("key", "like", "shopify.last_import.%")]).unlink()

    def _setup_import_idempotency_test(self) -> None:
        """Set up test data for import idempotency tests."""
        # Create test product with SKU
        self.test_product = self.env["product.product"].create({
            "name": "Test Product",
            "default_code": "80000002",  # Valid numeric SKU for line items
            "list_price": 100.0,
            "standard_price": 50.0,
        })
        
        # Create sync record for importers
        self.sync_record = self.env["shopify.sync"].create({
            "mode": "import_changed_orders",
        })

    def test_import_since_last_import_filters_correctly(self) -> None:
        """Test that import_since_last_import correctly filters by timestamp"""
        importer = OrderImporter(self.env, self.sync_record)

        # Create orders with different timestamps
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        new_time = datetime.now(timezone.utc)

        old_order_data = create_shopify_order_response(
            gid="gid://shopify/Order/old_order",
            name="#OLD-001",
            created_at=old_time.isoformat(),
            updated_at=old_time.isoformat(),
            customer=create_shopify_customer_response(gid="gid://shopify/Customer/old_cust", email="old@test.com"),
            line_items=[
                create_shopify_order_line_item_response(
                    sku=self.test_product.default_code,
                    variant_id="987654321",
                )
            ],
        )

        new_order_data = create_shopify_order_response(
            gid="gid://shopify/Order/new_order",
            name="#NEW-001",
            created_at=new_time.isoformat(),
            updated_at=new_time.isoformat(),
            customer=create_shopify_customer_response(gid="gid://shopify/Customer/new_cust", email="new@test.com"),
            line_items=[
                create_shopify_order_line_item_response(
                    sku=self.test_product.default_code,
                    variant_id="987654321",
                )
            ],
        )

        # Set up a timestamp between the two orders
        middle_time = old_time + timedelta(hours=1)
        config_key = last_import_config_key("order")
        self.env["ir.config_parameter"].set_param(config_key, format_datetime_for_shopify(middle_time))

        # Create mock that returns orders based on query filter
        def mock_fetch_page(_client: Any, query: str | None, cursor: str | None) -> MagicMock:
            mock_page = MagicMock()

            # Only return new order if filtering by time
            if query and 'updated_at:>"' in query:
                # Should only return the new order
                if cursor is None:
                    mock_page.nodes = [OrderFields(**new_order_data)]
                else:
                    mock_page.nodes = []
            else:
                # Return both orders if no filter
                if cursor is None:
                    mock_page.nodes = [OrderFields(**old_order_data), OrderFields(**new_order_data)]
                else:
                    mock_page.nodes = []

            mock_page.page_info = MagicMock()
            mock_page.page_info.has_next_page = False
            mock_page.page_info.end_cursor = None

            return mock_page

        with patch.object(importer, "_fetch_page", side_effect=mock_fetch_page):
            # Import since last import - should only get new order
            count = importer.import_orders_since_last_import()
            self.assertEqual(count, 1)

        # Verify only new order was imported (filter by shopify_order_id to exclude non-Shopify orders)
        orders = self.env["sale.order"].search([("shopify_order_id", "!=", False)])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].shopify_order_id, "new_order")
        self.assertEqual(orders[0].name, "#NEW-001")

    def test_first_import_gets_all_data(self) -> None:
        """Test that first import with no timestamp gets all data"""
        importer = OrderImporter(self.env, self.sync_record)

        # Create test data
        order_data = create_shopify_order_response(
            gid="gid://shopify/Order/first_order",
            name="#FIRST-001",
            customer=create_shopify_customer_response(gid="gid://shopify/Customer/first_cust", email="first@test.com"),
            line_items=[
                create_shopify_order_line_item_response(
                    sku=self.test_product.default_code,
                    variant_id="987654321",
                )
            ],
        )

        # Verify no timestamp exists
        config_key = last_import_config_key("order")
        self.assertFalse(self.env["ir.config_parameter"].get_param(config_key))

        # Create mock that returns order when no filter
        def mock_fetch_page(_client: Any, _query: str | None, cursor: str | None) -> MagicMock:
            mock_page = MagicMock()

            # First import has no timestamp, so query will have very old date
            if cursor is None:
                mock_page.nodes = [OrderFields(**order_data)]
            else:
                mock_page.nodes = []

            mock_page.page_info = MagicMock()
            mock_page.page_info.has_next_page = False
            mock_page.page_info.end_cursor = None

            return mock_page

        with patch.object(importer, "_fetch_page", side_effect=mock_fetch_page):
            # First import - should get the order
            count = importer.import_orders_since_last_import()
            self.assertEqual(count, 1)

        # Verify order was imported
        orders = self.env["sale.order"].search([("shopify_order_id", "=", "first_order")])
        self.assertEqual(len(orders), 1)
