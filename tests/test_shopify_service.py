import unittest
import importlib.util
import sys
from pathlib import Path
import types

httpx_stub = types.ModuleType('httpx')

class Client:
    pass

class Timeout:
    pass

class Limits:
    pass

class Request:
    pass

class Response:
    def __init__(self, status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.is_closed = False

    def read(self):
        pass

    def json(self):
        return {}

    def close(self):
        self.is_closed = True

httpx_stub.Client = Client
httpx_stub.Timeout = Timeout
httpx_stub.Limits = Limits
httpx_stub.Request = Request
httpx_stub.Response = Response
sys.modules['httpx'] = httpx_stub

odoo_stub = types.ModuleType('odoo')
odoo_api_stub = types.ModuleType('odoo.api')

class Environment:
    pass

odoo_api_stub.Environment = Environment
odoo_stub.api = odoo_api_stub
sys.modules['odoo'] = odoo_stub
sys.modules['odoo.api'] = odoo_api_stub

services_module = types.ModuleType('services')
shopify_package = types.ModuleType('services.shopify')
shopify_package.__path__ = [str(Path(__file__).parents[1] / 'services' / 'shopify')]
services_module.shopify = shopify_package
sys.modules['services'] = services_module
sys.modules['services.shopify'] = shopify_package

helpers_stub = types.ModuleType('services.shopify.helpers')

class ShopifyApiError(Exception):
    pass

helpers_stub.ShopifyApiError = ShopifyApiError
sys.modules['services.shopify.helpers'] = helpers_stub

for name in [
    'services.shopify.sync.deleters.product_deleter',
    'services.shopify.sync.exporters.product_exporter',
    'services.shopify.sync.importers.customer_importer',
    'services.shopify.sync.importers.order_importer',
    'services.shopify.sync.importers.product_importer',
]:
    sys.modules[name] = types.ModuleType(name)

gql_stub = types.ModuleType('services.shopify.gql')

class ShopifyClient:
    def __init__(self, http_client=None, url=None):
        pass

gql_stub.Client = ShopifyClient
sys.modules['services.shopify.gql'] = gql_stub

service_file = Path(__file__).parents[1] / 'services' / 'shopify' / 'service.py'
spec = importlib.util.spec_from_file_location('shopify_service', service_file)
shopify_service = importlib.util.module_from_spec(spec)
shopify_service.__package__ = 'services.shopify'
sys.modules['shopify_service'] = shopify_service
spec.loader.exec_module(shopify_service)
ShopifyService = shopify_service.ShopifyService

class DummyEnv:
    pass

class DummySyncRecord:
    id = 1
    hard_throttle_count = 0

class ShopifyServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ShopifyService(DummyEnv(), DummySyncRecord())

    def test_compute_throttle_delay_none_when_no_data(self):
        self.assertIsNone(self.service._compute_throttle_delay({}))

    def test_compute_throttle_delay_zero_when_sufficient_points(self):
        data = {
            'extensions': {
                'cost': {'throttleStatus': {'currentlyAvailable': self.service.MIN_API_POINTS}}
            }
        }
        self.assertEqual(self.service._compute_throttle_delay(data), 0.0)

    def test_compute_throttle_delay_calculates_delay(self):
        data = {
            'extensions': {
                'cost': {'throttleStatus': {'currentlyAvailable': 100, 'restoreRate': 50}}
            }
        }
        expected = max(
            min((self.service.MIN_API_POINTS - 100) / 50, self.service.MAX_SLEEP_TIME),
            self.service.MIN_SLEEP_TIME,
        )
        self.assertEqual(self.service._compute_throttle_delay(data), expected)

    def test_throttle_info_detects_throttled_error(self):
        data = {
            'errors': [{'extensions': {'code': 'THROTTLED'}, 'message': 'foo'}],
            'extensions': {'cost': {'throttleStatus': {'currentlyAvailable': 400}}},
        }
        throttled, delay = self.service._throttle_info(data)
        self.assertTrue(throttled)
        self.assertEqual(delay, self.service._compute_throttle_delay(data))

    def test_throttle_info_handles_non_throttled_error(self):
        data = {
            'errors': [{'message': 'bad'}],
            'extensions': {'cost': {'throttleStatus': {'currentlyAvailable': 600}}},
        }
        throttled, delay = self.service._throttle_info(data)
        self.assertFalse(throttled)
        self.assertEqual(delay, self.service._compute_throttle_delay(data))


if __name__ == '__main__':
    unittest.main()
