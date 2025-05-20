from odoo.tests import TransactionCase
from ..shopify.service import ShopifyService


class DummySync:
    def __init__(self) -> None:
        self.id = 1
        self.hard_throttle_count = 0


class TestShopifyService(TransactionCase):
    test_tags = {"-at_install", "-post_install"}

    def _service(self) -> ShopifyService:
        return ShopifyService(self.env, DummySync())

    def test_compute_throttle_delay_none(self) -> None:
        service = self._service()
        self.assertIsNone(service._compute_throttle_delay({}))

    def test_compute_throttle_delay_zero(self) -> None:
        service = self._service()
        data = {"extensions": {"cost": {"throttleStatus": {"currentlyAvailable": service.MIN_API_POINTS}}}}
        self.assertEqual(service._compute_throttle_delay(data), 0.0)

    def test_compute_throttle_delay_bounds(self) -> None:
        service = self._service()
        data = {"extensions": {"cost": {"throttleStatus": {"currentlyAvailable": 100, "restoreRate": 25}}}}
        self.assertEqual(service._compute_throttle_delay(data), 16.0)
        data = {"extensions": {"cost": {"throttleStatus": {"currentlyAvailable": 0, "restoreRate": 0}}}}
        self.assertEqual(service._compute_throttle_delay(data), 60.0)
        data = {
            "extensions": {"cost": {"throttleStatus": {"currentlyAvailable": service.MIN_API_POINTS - 1, "restoreRate": 1000}}}
        }
        self.assertEqual(service._compute_throttle_delay(data), 1.0)

    def test_throttle_info_with_error(self) -> None:
        service = self._service()
        data = {
            "errors": [{"extensions": {"code": "THROTTLED"}}],
            "extensions": {"cost": {"throttleStatus": {"currentlyAvailable": 400, "restoreRate": 10}}},
        }
        self.assertEqual(service._throttle_info(data), (True, 10.0))

    def test_throttle_info_without_error(self) -> None:
        service = self._service()
        data = {"extensions": {"cost": {"throttleStatus": {"currentlyAvailable": 499, "restoreRate": 1000}}}}
        self.assertEqual(service._throttle_info(data), (False, 1.0))
