"""Base type definitions and constants for test utilities."""

from datetime import datetime
from typing import Any, Union
from unittest.mock import MagicMock, Mock

# Type alias for values that can be passed to Odoo create/write methods
# This covers all standard Odoo field types
OdooValue = Union[
    str,  # Char, Text, Html fields
    int,  # Integer, Many2one (ID) fields
    float,  # Float, Monetary fields
    bool,  # Boolean fields
    None,  # Empty/unset fields
    list,  # One2many, Many2many fields (special tuples like [(6, 0, ids)])
    tuple,  # Command tuples for relational fields
    datetime,  # Datetime fields
    bytes,  # Binary fields
]

# Note: When using with **kwargs, the type checker interprets this as:
# **kwargs: OdooValue means kwargs is dict[str, OdooValue]
# This is the standard pattern for typing homogeneous kwargs values

# Common mock types for test methods
MockType = Union[MagicMock, Mock]

# Dict for test assertions and comparisons
AssertionDict = dict[str, Any]

# Common test context values to disable side effects
DEFAULT_TEST_CONTEXT = {
    "skip_shopify_sync": True,  # Skip Shopify API calls
    "tracking_disable": True,  # Disable mail tracking
    "no_reset_password": True,  # Skip password reset emails
    "mail_create_nosubscribe": True,  # Skip subscription emails
    "mail_create_nolog": True,  # Skip mail logging
    "mail_notrack": True,  # Disable mail tracking
}

# Standard test tags for different test types
STANDARD_TAGS = ["post_install", "-at_install"]
UNIT_TAGS = STANDARD_TAGS + ["unit_test"]
INTEGRATION_TAGS = STANDARD_TAGS + ["integration_test"]
TOUR_TAGS = STANDARD_TAGS + ["tour_test"]
PERFORMANCE_TAGS = STANDARD_TAGS + ["performance_test"]

# Common test data constants
TEST_SKU_PREFIX = "TEST"
TEST_SHOPIFY_ID_MIN = 1000000000
TEST_SHOPIFY_ID_MAX = 9999999999
