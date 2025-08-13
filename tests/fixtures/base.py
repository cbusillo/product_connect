from contextlib import contextmanager
from typing import Iterator, Any

from odoo.models import BaseModel
from odoo.api import Environment
from ..common_imports import (
    TransactionCase,
    HttpCase,
    MagicMock,
    patch,
    DEFAULT_TEST_CONTEXT,
    tagged,
    UNIT_TAGS,
    INTEGRATION_TAGS,
    TOUR_TAGS,
)


class _ShopifyMockMixin:
    def _setup_shopify_mocks(self) -> None:
        self.shopify_service_patcher = patch("odoo.addons.product_connect.services.shopify.sync.base.ShopifyService")
        self.mock_shopify_service_class = self.shopify_service_patcher.start()

        self.mock_client = MagicMock()
        self.mock_service_instance = MagicMock()
        self.mock_service_instance.client = self.mock_client
        self.mock_service_instance.first_location_gid = "gid://shopify/Location/12345"
        self.mock_service_instance.get_first_location_gid.return_value = "gid://shopify/Location/12345"

        self.mock_shopify_service_class.return_value = self.mock_service_instance

    def _teardown_shopify_mocks(self) -> None:
        if hasattr(self, "shopify_service_patcher") and self.shopify_service_patcher:
            self.shopify_service_patcher.stop()


@tagged(*UNIT_TAGS)
class UnitTestCase(_ShopifyMockMixin, TransactionCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                **DEFAULT_TEST_CONTEXT,
            )
        )

    def tearDown(self) -> None:
        self._teardown_shopify_mocks()
        super().tearDown()

    def mock_service(self, service_path: str) -> MagicMock:
        patcher = patch(service_path)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    @contextmanager
    def mock_shopify_client(self) -> Iterator[MagicMock]:
        with patch("addons.product_connect.services.shopify.client.GraphQLClient") as mock_client:
            instance = MagicMock()
            mock_client.return_value = instance
            yield instance

    def assertRecordValues(self, record: BaseModel, expected_values: dict) -> None:
        for field, expected in expected_values.items():
            actual = record[field]
            if hasattr(actual, "id"):
                actual = actual.id
            elif hasattr(actual, "ids"):
                actual = actual.ids

            self.assertEqual(actual, expected, f"Field '{field}' mismatch: expected {expected}, got {actual}")


def _get_or_create_geo_data(env: Environment) -> tuple[Any, Any, Any]:
    usa_country = env["res.country"].search([("code", "=", "US")], limit=1)
    if not usa_country:
        usa_country = env["res.country"].create({"name": "United States", "code": "US", "phone_code": 1})

    ny_state = env["res.country.state"].search([("code", "=", "NY"), ("country_id", "=", usa_country.id)], limit=1)
    if not ny_state:
        ny_state = env["res.country.state"].create({"name": "New York", "code": "NY", "country_id": usa_country.id})

    shopify_category = env["res.partner.category"].search([("name", "=", "Shopify")], limit=1)
    if not shopify_category:
        shopify_category = env["res.partner.category"].create({"name": "Shopify"})

    return usa_country, ny_state, shopify_category


class _BaseDataMixin:
    def _setup_base_data(self) -> None:
        self.usa_country, self.ny_state, self.shopify_category = _get_or_create_geo_data(self.env)

    @classmethod
    def _setup_class_base_data(cls) -> None:
        cls.usa_country, cls.ny_state, cls.shopify_category = _get_or_create_geo_data(cls.env)


@tagged(*INTEGRATION_TAGS)
class IntegrationTestCase(_ShopifyMockMixin, _BaseDataMixin, TransactionCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        test_context = DEFAULT_TEST_CONTEXT.copy()
        test_context["skip_shopify_sync"] = True
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                **test_context,
            )
        )
        cls._setup_test_data()

    @classmethod
    def _setup_test_data(cls) -> None:
        cls.test_company = cls.env.ref("base.main_company")

        cls.test_warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.test_company.id)], limit=1)

        cls.test_pricelist = cls.env["product.pricelist"].search([("currency_id.name", "=", "USD")], limit=1)
        if not cls.test_pricelist:
            cls.test_pricelist = cls.env["product.pricelist"].create(
                {
                    "name": "Test Pricelist",
                    "currency_id": cls.env.ref("base.USD").id,
                }
            )

        cls._setup_class_base_data()
        cls._reset_sku_sequence()

    @classmethod
    def _reset_sku_sequence(cls) -> None:
        sequence = cls.env["ir.sequence"].search([("code", "=", "product.template.default_code")], limit=1)
        if sequence:
            sequence.sudo().write({"number_next": 800000})

    def create_shopify_credentials(self) -> None:
        config_param = self.env["ir.config_parameter"].sudo()
        config_param.set_param("shopify.shop_url_key", "test-store.myshopify.com")
        config_param.set_param("shopify.webhook_key", "test_webhook_key")
        config_param.set_param("shopify.test_store", "1")

    @staticmethod
    def mock_shopify_response(data: dict | None = None, errors: list | None = None) -> dict:
        response = {"data": data or {}}
        if errors:
            response["errors"] = errors
        return response

    def tearDown(self) -> None:
        self._teardown_shopify_mocks()
        super().tearDown()


@tagged(*TOUR_TAGS)
class TourTestCase(HttpCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._setup_test_user()

    @classmethod
    def _setup_test_user(cls) -> None:
        import secrets
        import string

        try:
            admin_user = cls.env.ref("base.user_admin")
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            password = "Admin" + "".join(secrets.choice(alphabet) for _ in range(8)) + "!"
            admin_user.password = password
            cls.test_user = admin_user
            cls._test_user_password = password
            return
        except (ValueError, Exception):
            pass

        test_user = cls.env["res.users"].search([("login", "=", "tour_test_user"), ("active", "=", True)], limit=1)

        if not test_user:
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            password = "Test" + "".join(secrets.choice(alphabet) for _ in range(8)) + "!"

            try:
                group_ids = [cls.env.ref("base.group_user").id]  # Basic user access

                try:
                    group_ids.append(cls.env.ref("base.group_system").id)
                except ValueError:
                    pass

                try:
                    group_ids.append(cls.env.ref("stock.group_stock_user").id)
                except ValueError:
                    pass

                test_user = cls.env["res.users"].create(
                    {
                        "name": "Tour Test User",
                        "login": "tour_test_user",
                        "password": password,
                        "email": "tour.test@example.com",
                        "groups_id": [(6, 0, group_ids)],
                    }
                )
            except Exception:
                test_user = cls.env["res.users"].create(
                    {
                        "name": "Tour Test User",
                        "login": "tour_test_user",
                        "password": password,
                        "email": "tour.test@example.com",
                    }
                )
            cls._test_user_password = password
        else:
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            password = "Test" + "".join(secrets.choice(alphabet) for _ in range(8)) + "!"
            test_user.password = password
            cls._test_user_password = password

        cls.test_user = test_user

    def setUp(self) -> None:
        super().setUp()
        self.browser_size = "1920x1080"
        self.tour_timeout = 120

    def start_tour(self, url: str, tour_name: str, login: str | None = None, timeout: int | None = None) -> None:
        if timeout is None:
            timeout = self.tour_timeout

        login = self.test_user.login

        self.browser_js(
            url,
            f"odoo.__DEBUG__.services['web_tour.tour'].run('{tour_name}')",
            f"odoo.__DEBUG__.services['web_tour.tour'].tours['{tour_name}'].ready",
            login=login,
            timeout=timeout,
        )

    def register_tour(self, tour_definition: dict) -> None:
        pass

    def take_screenshot(self, name: str = "screenshot") -> None:
        pass
