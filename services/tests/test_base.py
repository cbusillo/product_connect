from unittest.mock import patch, MagicMock
from odoo.tests import TransactionCase


class ShopifyTestBase(TransactionCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.env = cls.env(context={"skip_shopify_sync": True})

    def setUp(self) -> None:
        super().setUp()
        self.shopify_service_patcher = None  # Initialize to None
        self._setup_base_data()

    def _setup_shopify_mocks(self) -> None:
        self.shopify_service_patcher = patch("odoo.addons.product_connect.services.shopify.sync.base.ShopifyService")
        self.mock_shopify_service_class = self.shopify_service_patcher.start()

        self.mock_client = MagicMock()
        self.mock_service_instance = MagicMock()
        self.mock_service_instance.client = self.mock_client
        self.mock_service_instance.first_location_gid = "gid://shopify/Location/12345"
        self.mock_service_instance.get_first_location_gid.return_value = "gid://shopify/Location/12345"

        self.mock_shopify_service_class.return_value = self.mock_service_instance

    def _setup_base_data(self) -> None:
        self.usa_country = self.env["res.country"].search([("code", "=", "US")], limit=1)
        if not self.usa_country:
            self.usa_country = self.env["res.country"].create({"name": "United States", "code": "US", "phone_code": 1})

        self.ny_state = self.env["res.country.state"].search(
            [("code", "=", "NY"), ("country_id", "=", self.usa_country.id)], limit=1
        )
        if not self.ny_state:
            self.ny_state = self.env["res.country.state"].create(
                {"name": "New York", "code": "NY", "country_id": self.usa_country.id}
            )

        self.shopify_category = self.env["res.partner.category"].search([("name", "=", "Shopify")], limit=1)
        if not self.shopify_category:
            self.shopify_category = self.env["res.partner.category"].create({"name": "Shopify"})

    def tearDown(self) -> None:
        if hasattr(self, "shopify_service_patcher") and self.shopify_service_patcher:
            self.shopify_service_patcher.stop()
        super().tearDown()
