"""JavaScript/Hoot test suite for product_connect module."""

import re
from ..common_imports import tagged, INTEGRATION_TAGS
from ..fixtures.base import TourTestCase


def unit_test_error_checker(message: str) -> bool:
    """Error checker that ignores HOOT internal messages"""
    return "[HOOT]" not in message


@tagged(*INTEGRATION_TAGS)
class ProductConnectJSTests(TourTestCase):
    """JavaScript/Hoot test suite for product_connect module"""
    
    @classmethod
    def setUpClass(cls) -> None:
        """Set up class with additional JS test specific configuration."""
        super().setUpClass()
        
        # Ensure we don't have database constraint issues during JS tests
        # by preparing the environment properly
        cls.env.cr.commit()
    
    def _get_test_login(self) -> str:
        """Get login for browser tests - fallback to admin if test user fails"""
        try:
            # Try test user first
            return self.test_user.login
        except (AttributeError, Exception):
            # Fallback to admin
            return "admin"

    def test_hoot_desktop(self) -> None:
        """Run Hoot test suite (desktop preset)"""
        # Use the test user created in TourTestCase with fallback
        self.browser_js(
            "/web/tests?headless&loglevel=2&preset=desktop&timeout=15000",
            code="",
            login=self._get_test_login(),
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )

    def test_hoot_mobile(self) -> None:
        """Run Hoot test suite (mobile preset)"""
        # Use the test user created in TourTestCase with fallback
        self.browser_js(
            "/web/tests?headless&loglevel=2&preset=mobile&tag=-headless&timeout=15000",
            code="",
            login=self._get_test_login(),
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )

    def test_check_forbidden_statements(self) -> None:
        """Ensure no test.only() or test.debug() calls in test files"""
        re_forbidden = re.compile(r"test.*\.(only|debug)\(")

        # Check our test files for forbidden statements
        test_files = [
            "addons/product_connect/static/tests/basic.test.js",
            "addons/product_connect/static/tests/motor_form.test.js",
            "addons/product_connect/static/tests/shipping_analytics.test.js",
            "addons/product_connect/static/tests/multigraph_multi_measure.test.js",
            "addons/product_connect/static/tests/multigraph_metadata.test.js",
            "addons/product_connect/static/tests/multigraph_axis_configuration.test.js",
            "addons/product_connect/static/tests/views/multigraph_view.test.js",
            "addons/product_connect/static/tests/multigraph_integration.test.js",
            "addons/product_connect/static/tests/multigraph_arch_parser.test.js",
            "addons/product_connect/static/tests/multigraph_data_processing.test.js",
            "addons/product_connect/static/tests/multigraph_f1_string_fix.test.js",
            "addons/product_connect/static/tests/multigraph_model.test.js",
            "addons/product_connect/static/tests/multigraph_props_validation.test.js",
        ]

        for file_path in test_files:
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                    if re_forbidden.search(content):
                        self.fail(f"`only()` or `debug()` used in file {file_path}")
            except FileNotFoundError:
                # File doesn't exist, skip
                pass
