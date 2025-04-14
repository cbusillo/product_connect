import logging

from time import sleep

from httpx import Client, Timeout, Limits, Request, Response
from odoo.api import Environment

from ..utils.shopify_helpers import ShopifyApiError
from .shopify_client import Client as ShopifyClient


_logger = logging.getLogger(__name__)


class ShopifyService:
    MIN_SHOPIFY_REMAINING_API_POINTS = 500
    MAX_RETRY_ATTEMPTS = 10
    MIN_SLEEP_TIME = 0.5
    MAX_SLEEP_TIME = 60

    def __init__(self, env: Environment):
        self.env = env
        self._client: ShopifyClient | None = None
        self.first_location_gid: str | None = None

    @property
    def client(self) -> ShopifyClient:
        if self._client is None:
            self._create_client()

        return self._client

    def get_first_location_gid(self) -> str:
        client = self.client
        shopify_response = client.get_locations()
        edges = shopify_response.locations.edges
        if not edges:
            raise ShopifyApiError("No locations found in the Shopify store.")

        location_gid = edges[0].node.id
        if not location_gid:
            raise ShopifyApiError("Location GID not found in the Shopify response.")

        return location_gid

    def _create_client(self) -> ShopifyClient:
        shop_url_key = self.env["ir.config_parameter"].sudo().get_param("shopify.shop_url_key")
        api_token = self.env["ir.config_parameter"].sudo().get_param("shopify.api_token")
        api_version = self.env["ir.config_parameter"].sudo().get_param("shopify.api_version")

        if not all([shop_url_key, api_token, api_version]):
            raise ShopifyApiError(
                "Shopify API credentials (shopify.shop_url_key, shopify.api_token, and shopify.api_version) are not set. Please configure them in the Odoo settings."
            )

        endpoint = f"https://{shop_url_key}.myshopify.com/admin/api/{api_version}/graphql.json"
        http_client = self._create_http_client(api_token)
        client = ShopifyClient(http_client=http_client, url=endpoint)
        self._client = client
        self.first_location_gid = self.get_first_location_gid()
        return client

    def _create_http_client(self, api_token: str) -> Client:
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": api_token,
        }
        timeout = Timeout(30.0, connect=10.0)
        limits = Limits(max_connections=10, max_keepalive_connections=5)

        def rate_limit_hook(response: Response) -> None:
            if response.status_code != 200:
                raise ShopifyApiError(f"Shopify API request failed with status code {response.status_code}")

            response.read()
            data = response.json()

            if "extensions" in data:
                throttle_status = data.get("extensions", {}).get("cost", {}).get("throttleStatus", {})
                currently_available = throttle_status.get("currentlyAvailable", 0)
                restore_rate = throttle_status.get("restoreRate", 1)
                _logger.debug(f"Shopify API rate limit status: {throttle_status}")

                if currently_available < self.MIN_SHOPIFY_REMAINING_API_POINTS:
                    wait_time = (
                        (self.MIN_SHOPIFY_REMAINING_API_POINTS - currently_available) / restore_rate if restore_rate else 0
                    )
                    _logger.info(f"Low API points. Waiting for {wait_time:.2f} seconds...")
                    sleep(wait_time)

        client = Client(
            headers=headers,
            timeout=timeout,
            limits=limits,
            event_hooks={"response": [rate_limit_hook]},
        )

        original_send = client.send

        def send_with_retry(request: Request, **kwargs: object) -> Response:
            retries = 0
            response = original_send(request, **kwargs)
            while retries < self.MAX_RETRY_ATTEMPTS and response.status_code in {429, 500, 502, 503, 504}:
                wait_time = min(self.MAX_SLEEP_TIME, self.MIN_SLEEP_TIME * 2**retries)
                _logger.warning(
                    f"Retrying request after {response.status_code} error. Waiting for {wait_time:.2f} seconds on request {retries + 1} for URL {request.url}..."
                )
                sleep(wait_time)
                retries += 1
                response = original_send(request, **kwargs)

            if retries >= self.MAX_RETRY_ATTEMPTS:
                raise ShopifyApiError(f"Max retry attempts reached for request to {request.url}")
            return response

        client.send = send_with_retry
        return client
