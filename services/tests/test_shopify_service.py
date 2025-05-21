from typing import Callable
from unittest.mock import patch

from httpx import Request, Response
from odoo.tests import TransactionCase


from ..shopify.service import ShopifyService
from ..shopify import service as _service_module


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

    def test_get_first_location_gid(self) -> None:
        service = self._service()

        class Loc:
            def __init__(self, gid: str) -> None:
                self.id = gid

        class Response:
            def __init__(self, nodes: list[Loc]) -> None:
                self.nodes = nodes

        service._client = type("Client", (), {"get_locations": lambda self: Response([Loc("gid1")])})()
        self.assertEqual(service.get_first_location_gid(), "gid1")

    def test_get_first_location_gid_error(self) -> None:
        service = self._service()
        service._client = type("Client", (), {"get_locations": lambda self: type("Res", (), {"nodes": []})()})()
        with self.assertRaises(Exception):
            service.get_first_location_gid()

    def test_create_client_success_and_retry(self) -> None:
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("shopify.shop_url_key", "shop")
        config.set_param("shopify.api_token", "token")
        service = self._service()

        class DummyClient:
            def __init__(self, **_kw: object) -> None:
                self.event_hooks: dict[str, list[Callable[[Response], None]]] = {}
                self.send_calls: list[Request] = []
                self.send_func: Callable[[Request], Response] = lambda request: Response(200, request=request, json={})

            def send(self, request: Request, **_kw: object) -> Response:
                self.send_calls.append(request)
                return self.send_func(request)

        req = Request("GET", "http://t")
        responses = [Response(200, request=req, json={}), Response(200, request=req, json={})]

        def send_one(_request: Request) -> Response:
            return responses.pop(0)

        with patch.object(_service_module, "Client", DummyClient), patch.object(
            _service_module, "ShopifyClient", lambda http_client, url: http_client
        ), patch.object(_service_module, _service_module.sleep.__name__) as fake_sleep, patch.object(
            service, "get_first_location_gid", return_value="loc"
        ), patch.object(
            service, "_throttle_info", side_effect=[(True, None), (False, None)]
        ):
            client = service._create_client()
            self.assertIs(service._client, client)
            client.send_func = send_one
            result = client.send(req)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(len(client.send_calls), 2)
            fake_sleep.assert_called_with(1.0)
            self.assertEqual(service.sync_record.hard_throttle_count, 1)

    def test_create_client_missing_credentials(self) -> None:
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("shopify.shop_url_key", "")
        service = self._service()
        with self.assertRaises(Exception):
            service._create_client()
