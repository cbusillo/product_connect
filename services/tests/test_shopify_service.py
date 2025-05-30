from typing import Callable, Iterator, Tuple, cast
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

from httpx import Request, Response
from odoo.tests import TransactionCase, tagged


from ..shopify.service import ShopifyService
from ..shopify import service as _service_module
from ..shopify.helpers import ShopifyApiError


class DummySync:
    def __init__(self) -> None:
        self.id = 1
        self.hard_throttle_count = 0


class _BaseDummyClient:
    def __init__(self, **kw: object) -> None:
        self.event_hooks = kw.get("event_hooks", {})
        self.send_calls: list[Request] = []
        self.response = Response(200, request=Request("GET", "http://t"))

    def send(self, request: Request, **_kw: object) -> Response:
        self.send_calls.append(request)
        return self.response


@tagged("post_install", "-at_install")
class TestShopifyService(TransactionCase):
    def _service(self) -> ShopifyService:
        return ShopifyService(self.env, DummySync())

    @contextmanager
    def _client(
        self, service: ShopifyService, client_cls: type[_BaseDummyClient]
    ) -> Iterator[Tuple[_BaseDummyClient, MagicMock]]:
        with patch.object(_service_module, "Client", client_cls), patch.object(_service_module, "sleep") as fake_sleep:
            client = cast(_BaseDummyClient, service._create_http_client("t"))
            yield client, fake_sleep

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

        class LocationsResponse:
            def __init__(self, nodes: list[Loc]) -> None:
                self.nodes = nodes

        service._client = type(
            "LocationsClient",
            (),
            {"get_locations": lambda _client: LocationsResponse([Loc("gid1")])},
        )()
        self.assertEqual(service.get_first_location_gid(), "gid1")

    def test_get_first_location_gid_error(self) -> None:
        service = self._service()
        service._client = type(
            "LocationsClient",
            (),
            {"get_locations": lambda _client: type("LocationsResponse", (), {"nodes": []})()},
        )()
        with self.assertRaises(Exception):
            service.get_first_location_gid()

    def test_create_client_success_and_retry(self) -> None:
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("shopify.shop_url_key", "shop")
        config.set_param("shopify.api_token", "token")
        service = self._service()

        class DummyClient(_BaseDummyClient):
            def __init__(self, **_kw: object) -> None:
                super().__init__(**_kw)
                self.event_hooks = {}
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
            dummy_client = cast(DummyClient, client)
            self.assertIs(service._client, client)
            dummy_client.send_func = send_one
            result = dummy_client.send(req)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(len(dummy_client.send_calls), 2)
            fake_sleep.assert_called_with(1.0)
            self.assertEqual(service.sync_record.hard_throttle_count, 1)

    def test_create_client_missing_credentials(self) -> None:
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("shopify.shop_url_key", "")
        service = self._service()
        with self.assertRaises(Exception):
            service._create_client()

    def test_create_client_resets_on_location_error(self) -> None:
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("shopify.shop_url_key", "shop")
        config.set_param("shopify.api_token", "token")
        service = self._service()

        with patch.object(service, "get_first_location_gid", side_effect=ShopifyApiError("boom")):
            with self.assertRaises(ShopifyApiError):
                service._create_client()
        self.assertIsNone(service._client)

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

        class DummyClient(_BaseDummyClient):
            def __init__(self, **kw: object) -> None:
                super().__init__(**kw)
                self.send_func: Callable[[Request], Response] = lambda request: Response(200, request=request, json={})

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

        class DummyClient(_BaseDummyClient):
            def __init__(self, **kw: object) -> None:
                super().__init__(**kw)
                self.send_func = lambda request: Response(500, request=request)

            def send(self, request: Request, **_kw: object) -> Response:
                self.send_calls.append(request)
                return self.send_func(request)

        with self._client(service, DummyClient) as (client, fake_sleep):
            service.MAX_RETRY_ATTEMPTS = 1
            req = Request("GET", "http://t")
            with self.assertRaises(Exception):
                client.send(req)
            self.assertEqual(len(client.send_calls), 2)
            fake_sleep.assert_called()

    def test_send_with_retry_not_transient(self) -> None:
        service = self._service()

        class DummyClient(_BaseDummyClient):
            def __init__(self, **kw: object) -> None:
                super().__init__(**kw)
                self.response = Response(
                    404,
                    headers={"content-type": "application/json"},
                    request=Request("GET", "http://t"),
                )

        with self._client(service, DummyClient) as (client, fake_sleep):
            req = Request("GET", "http://t")
            result = client.send(req)
            self.assertIs(result, client.response)
            self.assertEqual(len(client.send_calls), 1)
            fake_sleep.assert_not_called()

    def test_send_with_retry_invalid_json(self) -> None:
        service = self._service()

        class DummyClient(_BaseDummyClient):
            def __init__(self, **kw: object) -> None:
                super().__init__(**kw)

                class Resp:
                    status_code = 200
                    headers = {"content-type": "application/json"}
                    request = Request("GET", "http://t")

                    def json(self) -> dict:
                        raise ValueError("bad")

                    def close(self) -> None:
                        pass

                self.response = Resp()

        with self._client(service, DummyClient) as (client, fake_sleep):
            req = Request("GET", "http://t")
            result = client.send(req)
            self.assertIs(result, client.response)
            self.assertEqual(len(client.send_calls), 1)
            fake_sleep.assert_not_called()

    def test_rate_limit_hook_no_json(self) -> None:
        service = self._service()

        class DummyClient(_BaseDummyClient):
            def __init__(self, **kw: object) -> None:
                super().__init__(**kw)

            def send(self, request: Request, **_kw: object) -> Response:
                return Response(200, request=request)

        class Resp:
            headers: dict[str, str] = {}

        with patch.object(_service_module, "Client", DummyClient), patch.object(_service_module, "sleep") as fake_sleep:
            client = service._create_http_client("t")
            hook = client.event_hooks["response"][0]
            hook(Resp())
            fake_sleep.assert_not_called()

    def test_rate_limit_hook_closed_or_no_wait(self) -> None:
        service = self._service()

        class DummyClient(_BaseDummyClient):
            def __init__(self, **kw: object) -> None:
                super().__init__(**kw)

            def send(self, request: Request, **_kw: object) -> Response:
                return Response(200, request=request)

        class Resp:
            def __init__(self, data: dict, closed: bool) -> None:
                self.headers = {"content-type": "application/json"}
                self._json = data
                self.is_closed = closed
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
            resp_closed = Resp({}, True)
            hook(resp_closed)
            self.assertFalse(resp_closed.read_called)

            resp_ok = Resp(
                {"extensions": {"cost": {"throttleStatus": {"currentlyAvailable": service.MIN_API_POINTS, "restoreRate": 1}}}},
                False,
            )
            hook(resp_ok)
            fake_sleep.assert_not_called()

    def test_send_with_retry_zero_attempts(self) -> None:
        service = self._service()
        service.MAX_RETRY_ATTEMPTS = -1

        class DummyClient(_BaseDummyClient):
            def __init__(self, **kw: object) -> None:
                super().__init__(**kw)

            def send(self, request: Request, **_kw: object) -> Response:
                return Response(200, request=request)

        with patch.object(_service_module, "Client", DummyClient), patch.object(_service_module, "sleep") as fake_sleep:
            client = service._create_http_client("t")
            req = Request("GET", "http://t")
            with self.assertRaises(ShopifyApiError):
                client.send(req)
            fake_sleep.assert_not_called()

    def test_send_with_retry_delay_no_hard_throttle(self) -> None:
        service = self._service()

        class DummyClient(_BaseDummyClient):
            def __init__(self, **kw: object) -> None:
                super().__init__(**kw)
                self.send_func: Callable[[Request], Response] = lambda request: Response(
                    200,
                    json={"extensions": {"cost": {"throttleStatus": {"currentlyAvailable": 400, "restoreRate": 1}}}},
                    request=request,
                    headers={"content-type": "application/json"},
                )

            def send(self, request: Request, **_kw: object) -> Response:
                return self.send_func(request)

        resp = Response(
            200,
            json={"extensions": {"cost": {"throttleStatus": {"currentlyAvailable": 400, "restoreRate": 1}}}},
            request=Request("GET", "http://t"),
            headers={"content-type": "application/json"},
        )

        responses = [resp, resp]

        def send_one(_request: Request) -> Response:
            return responses.pop(0)

        service.MAX_RETRY_ATTEMPTS = 1
        with patch.object(_service_module, "Client", DummyClient), patch.object(
            _service_module, "sleep"
        ) as fake_sleep, patch.object(service, "_throttle_info", side_effect=[(False, 2), (False, None)]):
            client = service._create_http_client("t")
            cast(DummyClient, client).send_func = send_one  # type: ignore
            req = Request("GET", "http://t")
            result = client.send(req)
            self.assertEqual(result.status_code, 200)
            fake_sleep.assert_called_once_with(2)
            self.assertEqual(service.sync_record.hard_throttle_count, 0)

    def test_send_with_retry_invalid_json_transient(self) -> None:
        service = self._service()

        class DummyClient(_BaseDummyClient):
            def __init__(self, **kw: object) -> None:
                super().__init__(**kw)

                class Resp:
                    status_code = 200
                    headers = {"content-type": "application/json"}
                    request = Request("GET", "http://t")

                    def json(self) -> dict:
                        raise ValueError("bad")

                    def close(self) -> None:
                        pass

                self.response = Resp()

        service.MAX_RETRY_ATTEMPTS = 0
        with patch.object(_service_module, "Client", DummyClient), patch.object(
            _service_module, "sleep"
        ) as fake_sleep, patch.object(_service_module, "THROTTLE_TRANSIENT_STATUS", {200}):
            client = service._create_http_client("t")
            req = Request("GET", "http://t")
            with self.assertRaises(ShopifyApiError):
                client.send(req)
            fake_sleep.assert_not_called()
