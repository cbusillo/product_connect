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
        ), patch.object(_service_module, "sleep") as fake_sleep, patch.object(
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

    def test_client_property_creates_client(self) -> None:
        service = self._service()

        def create_client() -> str:
            service._client = "cli"
            return "cli"

        with patch.object(service, "_create_client", side_effect=create_client) as create:
            service._client = None
            self.assertEqual(service.client, "cli")
            create.assert_called_once()

    def test_get_first_location_gid_no_id(self) -> None:
        service = self._service()

        class Loc:
            id = None

        class Res:
            nodes = [Loc()]

        service._client = type("C", (), {"get_locations": lambda self: Res()})()
        with self.assertRaises(Exception):
            service.get_first_location_gid()

    def test_rate_limit_hook_waits(self) -> None:
        service = self._service()

        class DummyClient:
            def __init__(self, **kw: object) -> None:
                self.event_hooks = kw.get("event_hooks", {})
                self.send_func = lambda request: Response(200, request=request, json={})
                self.send_calls: list[Request] = []

            def send(self, request: Request, **_kw: object) -> Response:
                self.send_calls.append(request)
                return self.send_func(request)

        class FakeResponse:
            def __init__(self, json_data: dict) -> None:
                self.headers = {"content-type": "application/json"}
                self.status_code = 200
                self._json = json_data
                self.is_closed = False
                self.read_called = False
                self.request = Request("GET", "http://t")

            def read(self) -> None:
                self.read_called = True
                self.is_closed = True

            def json(self) -> dict:
                return self._json

            def close(self) -> None:
                self.is_closed = True

        with patch.object(_service_module, "Client", DummyClient), patch.object(_service_module, "sleep") as fake_sleep:
            client = service._create_http_client("t")
            hook = client.event_hooks["response"][0]
            resp = FakeResponse({"extensions": {"cost": {"throttleStatus": {"currentlyAvailable": 100, "restoreRate": 2}}}})
            hook(resp)
            self.assertTrue(resp.read_called)
            fake_sleep.assert_called_once()

    def test_send_with_retry_transient_error(self) -> None:
        service = self._service()

        class DummyClient:
            def __init__(self, **kw: object) -> None:
                self.event_hooks = kw.get("event_hooks", {})
                self.send_func = lambda request: Response(500, request=request)
                self.send_calls: list[Request] = []

            def send(self, request: Request, **_kw: object) -> Response:
                self.send_calls.append(request)
                return self.send_func(request)

        with patch.object(_service_module, "Client", DummyClient), patch.object(_service_module, "sleep") as fake_sleep:
            service.MAX_RETRY_ATTEMPTS = 1
            client = service._create_http_client("t")
            req = Request("GET", "http://t")
            with self.assertRaises(Exception):
                client.send(req)
            self.assertEqual(len(client.send_calls), 2)
            fake_sleep.assert_called()

    def test_send_with_retry_not_transient(self) -> None:
        service = self._service()

        class DummyClient:
            def __init__(self, **kw: object) -> None:
                self.event_hooks = kw.get("event_hooks", {})
                self.send_calls: list[Request] = []
                self.response = Response(404, headers={"content-type": "application/json"}, request=Request("GET", "http://t"))

            def send(self, request: Request, **_kw: object) -> Response:
                self.send_calls.append(request)
                return self.response

        with patch.object(_service_module, "Client", DummyClient), patch.object(_service_module, "sleep") as fake_sleep:
            client = service._create_http_client("t")
            req = Request("GET", "http://t")
            result = client.send(req)
            self.assertIs(result, client.response)
            self.assertEqual(len(client.send_calls), 1)
            fake_sleep.assert_not_called()

    def test_send_with_retry_invalid_json(self) -> None:
        service = self._service()

        class DummyClient:
            def __init__(self, **kw: object) -> None:
                self.event_hooks = kw.get("event_hooks", {})
                self.send_calls: list[Request] = []

                class Resp:
                    status_code = 200
                    headers = {"content-type": "application/json"}
                    request = Request("GET", "http://t")

                    def json(self) -> dict:
                        raise ValueError("bad")

                    def close(self) -> None:
                        pass

                self.response = Resp()

            def send(self, request: Request, **_kw: object) -> Response:
                self.send_calls.append(request)
                return self.response

        with patch.object(_service_module, "Client", DummyClient), patch.object(_service_module, "sleep") as fake_sleep:
            client = service._create_http_client("t")
            req = Request("GET", "http://t")
            result = client.send(req)
            self.assertIs(result, client.response)
            self.assertEqual(len(client.send_calls), 1)
            fake_sleep.assert_not_called()

    def test_rate_limit_hook_no_json(self) -> None:
        service = self._service()

        class DummyClient:
            def __init__(self, **kw: object) -> None:
                self.event_hooks = kw.get("event_hooks", {})

            def send(self, request: Request, **_kw: object) -> Response:
                return Response(200, request=request)

        class Resp:
            headers: dict[str, str] = {}

        with patch.object(_service_module, "Client", DummyClient), patch.object(_service_module, "sleep") as fake_sleep:
            client = service._create_http_client("t")
            hook = client.event_hooks["response"][0]
            hook(Resp())
            fake_sleep.assert_not_called()
