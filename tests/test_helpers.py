"""Common test helper functions and utilities."""

import contextlib
import random
import secrets
import string
import time
from datetime import datetime
from typing import Any, Generator, Optional
from unittest.mock import MagicMock, patch

from .base_types import TEST_SHOPIFY_ID_MAX, TEST_SHOPIFY_ID_MIN


def generate_unique_sku(prefix: Optional[str] = None) -> str:
    """Generate a unique SKU for testing.

    Args:
        prefix: Optional prefix for the SKU. Not used anymore as SKUs must be numeric only.

    Returns:
        A unique SKU string (4-8 digits, numeric only).
    """
    # SKUs must be 4-8 digits only per product_template validation
    return str(random.randint(10000000, 99999999))  # 8-digit numeric SKU


def generate_unique_name(base_name: str) -> str:
    """Generate a unique name using timestamp.

    Args:
        base_name: Base name to make unique.

    Returns:
        Unique name with timestamp suffix.
    """
    return f"{base_name} {datetime.now().timestamp()}"


def generate_shopify_id() -> str:
    """Generate a valid Shopify ID for testing.

    Returns:
        A string representing a Shopify ID.
    """
    return str(random.randint(TEST_SHOPIFY_ID_MIN, TEST_SHOPIFY_ID_MAX))


def generate_motor_serial() -> str:
    """Generate a motor serial number.

    Returns:
        A motor serial number like 'ABC1234567'.
    """
    letters = "".join(random.choices(string.ascii_uppercase, k=3))
    numbers = "".join(random.choices(string.digits, k=7))
    return f"{letters}{numbers}"


def generate_secure_token(length: int = 32) -> str:
    """Generate a secure random token for testing.

    Args:
        length: Length of the token. Defaults to 32.

    Returns:
        A secure random token string.
    """
    return secrets.token_urlsafe(length)


def assert_shopify_fields(record: object, expected: dict[str, object]) -> None:
    """Assert that Shopify fields match expected values.

    Args:
        record: Odoo record to check.
        expected: Dictionary of field names to expected values.

    Raises:
        AssertionError: If any field doesn't match.
    """
    for field, value in expected.items():
        actual = getattr(record, field)
        assert actual == value, f"Field {field}: expected {value!r}, got {actual!r}"


def with_test_context(env: "odoo.api.Environment") -> "odoo.api.Environment":
    """Add standard test context to environment.

    Args:
        env: Odoo environment.

    Returns:
        Environment with test context applied.
    """
    from .base_types import DEFAULT_TEST_CONTEXT

    return env.with_context(**DEFAULT_TEST_CONTEXT)


# ============================================================================
# Mock Helper Context Managers
# ============================================================================


@contextlib.contextmanager
def mock_shopify_service(
    return_value: Any = None,
    side_effect: Any = None,
) -> Generator[MagicMock, None, None]:
    """Mock the Shopify service for testing.

    Args:
        return_value: Value to return from mocked methods.
        side_effect: Side effect for mocked methods.

    Yields:
        The mocked Shopify service.
    """
    with patch("product_connect.services.shopify.ShopifyService") as mock_service:
        if return_value is not None:
            mock_service.return_value = return_value
        if side_effect is not None:
            mock_service.side_effect = side_effect
        yield mock_service


@contextlib.contextmanager
def mock_graphql_client(
    execute_return: Optional[dict] = None,
    execute_side_effect: Any = None,
) -> Generator[MagicMock, None, None]:
    """Mock the GraphQL client for testing.

    Args:
        execute_return: Return value for execute method.
        execute_side_effect: Side effect for execute method.

    Yields:
        The mocked GraphQL client.
    """
    with patch("product_connect.services.shopify.gql.Client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance

        if execute_return is not None:
            mock_instance.execute.return_value = execute_return
        if execute_side_effect is not None:
            mock_instance.execute.side_effect = execute_side_effect

        yield mock_instance


@contextlib.contextmanager
def mock_datetime_now(fixed_datetime: datetime) -> Generator[None, None, None]:
    """Mock datetime.now() to return a fixed time.

    Args:
        fixed_datetime: The datetime to return.

    Yields:
        None
    """
    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_datetime
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        yield


# ============================================================================
# Enhanced Assertion Helpers
# ============================================================================


def assert_fields_equal(
    record: object,
    expected: dict[str, Any],
    message_prefix: str = "",
) -> None:
    """Assert multiple fields equal with detailed error messages.

    Args:
        record: Odoo record to check.
        expected: Dictionary of field names to expected values.
        message_prefix: Optional prefix for error messages.

    Raises:
        AssertionError: If any field doesn't match.
    """
    errors = []
    for field, expected_value in expected.items():
        actual_value = getattr(record, field, None)
        if actual_value != expected_value:
            error = f"Field '{field}': expected {expected_value!r}, got {actual_value!r}"
            if message_prefix:
                error = f"{message_prefix} - {error}"
            errors.append(error)

    if errors:
        raise AssertionError("\n".join(errors))


def assert_record_count(
    model: object,
    domain: list,
    expected_count: int,
    message: Optional[str] = None,
) -> None:
    """Assert the count of records matching a domain.

    Args:
        model: Odoo model to search.
        domain: Search domain.
        expected_count: Expected number of records.
        message: Optional custom error message.

    Raises:
        AssertionError: If count doesn't match.
    """
    actual_count = model.search_count(domain)
    if actual_count != expected_count:
        msg = message or f"Expected {expected_count} records, found {actual_count}"
        msg += f"\nDomain: {domain}"
        raise AssertionError(msg)


def assert_in_log(
    log_records: list,
    expected_message: str,
    level: Optional[str] = None,
) -> None:
    """Assert a message appears in log records.

    Args:
        log_records: List of log records from caplog.
        expected_message: Message to search for.
        level: Optional log level to match.

    Raises:
        AssertionError: If message not found.
    """
    for record in log_records:
        if expected_message in record.message:
            if level is None or record.levelname == level:
                return

    msg = f"Expected log message not found: {expected_message!r}"
    if level:
        msg += f" at level {level}"
    raise AssertionError(msg)


# ============================================================================
# Performance Measurement
# ============================================================================


@contextlib.contextmanager
def measure_performance(
    operation_name: str,
    max_duration: Optional[float] = None,
) -> Generator[dict[str, Any], None, None]:
    """Measure the performance of a code block.

    Args:
        operation_name: Name of the operation being measured.
        max_duration: Optional maximum allowed duration in seconds.

    Yields:
        Dictionary with timing information.

    Raises:
        AssertionError: If max_duration is exceeded.
    """
    metrics = {
        "operation": operation_name,
        "start_time": time.perf_counter(),
        "end_time": None,
        "duration": None,
    }

    try:
        yield metrics
    finally:
        metrics["end_time"] = time.perf_counter()
        metrics["duration"] = metrics["end_time"] - metrics["start_time"]

        if max_duration and metrics["duration"] > max_duration:
            raise AssertionError(
                f"Operation '{operation_name}' took {metrics['duration']:.3f}s, exceeding maximum of {max_duration:.3f}s"
            )


# ============================================================================
# Test Data Builders
# ============================================================================


class TestDataBuilder:
    """Builder for creating consistent test data."""

    @staticmethod
    def shopify_response(
        data: Optional[dict] = None,
        errors: Optional[list] = None,
        extensions: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Build a Shopify GraphQL response.

        Args:
            data: Response data.
            errors: Response errors.
            extensions: Response extensions.

        Returns:
            Formatted Shopify response.
        """
        response = {}
        if data is not None:
            response["data"] = data
        if errors is not None:
            response["errors"] = errors
        if extensions is not None:
            response["extensions"] = extensions
        return response

    @staticmethod
    def shopify_product(
        product_id: Optional[str] = None,
        title: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build a Shopify product data structure.

        Args:
            product_id: Shopify product ID.
            title: Product title.
            **kwargs: Additional product fields.

        Returns:
            Shopify product dict.
        """
        product = {
            "id": product_id or generate_shopify_id(),
            "title": title or generate_unique_name("Test Product"),
            "handle": kwargs.get("handle", "test-product"),
            "vendor": kwargs.get("vendor", "Test Vendor"),
            "productType": kwargs.get("productType", "Test Type"),
            "tags": kwargs.get("tags", []),
            "status": kwargs.get("status", "ACTIVE"),
        }
        product.update(kwargs)
        return product
