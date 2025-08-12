"""Common imports for test files.

This module provides a single import point for commonly used test utilities.
Import from here to reduce duplication and ensure consistency.

Example usage:
    from .common_imports import *
    # or more explicitly:
    from .common_imports import datetime, MagicMock, patch, tagged
"""

# Standard library imports
import logging
import random
import secrets
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Iterator, Optional
from unittest.mock import MagicMock, Mock, PropertyMock, patch

# Odoo test framework
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

# Re-export our base types for convenience
from .base_types import (
    INTEGRATION_TAGS,
    STANDARD_TAGS,
    TEST_SHOPIFY_ID_MAX,
    TEST_SHOPIFY_ID_MIN,
    TEST_SKU_PREFIX,
    TOUR_TAGS,
    UNIT_TAGS,
    AssertionDict,
    DEFAULT_TEST_CONTEXT,
    MockType,
    OdooValue,
)

__all__ = [
    # Standard library
    "date",
    "datetime",
    "timedelta",
    "Decimal",
    "logging",
    "random",
    "secrets",
    "time",
    # Typing
    "Any",
    "Callable",
    "Iterator",
    "Optional",
    # Mocking
    "MagicMock",
    "Mock",
    "PropertyMock",
    "patch",
    # Odoo
    "tagged",
    "TransactionCase",
    "HttpCase",
    "ValidationError",
    "UserError",
    "AccessError",
    # Our types and constants
    "OdooValue",
    "MockType",
    "AssertionDict",
    "DEFAULT_TEST_CONTEXT",
    "STANDARD_TAGS",
    "UNIT_TAGS",
    "INTEGRATION_TAGS",
    "TOUR_TAGS",
    "TEST_SKU_PREFIX",
    "TEST_SHOPIFY_ID_MIN",
    "TEST_SHOPIFY_ID_MAX",
]
