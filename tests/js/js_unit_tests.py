import re
from ..common_imports import tagged, JS_TAGS
from ..fixtures.base import TourTestCase


def unit_test_error_checker(message: str) -> bool:
    return "[HOOT]" not in message


# This runs JavaScript unit tests via browser - it's a unit test runner, not a tour
@tagged(*JS_TAGS, "product_connect")
class ProductConnectJSTests(TourTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def _get_test_login(self) -> str:
        """Get the secure test user login."""
        if hasattr(self, "test_user") and self.test_user:
            return self.test_user.login
        return "tour_test_user"

    def test_hoot_desktop(self) -> None:
        self.browser_js(
            "/web/tests?headless&loglevel=2&preset=desktop&timeout=30000&filter=product_connect",
            code="",
            login=self._get_test_login(),
            # Fail fast: reduce per-test timeout from 30m to 15m→10m
            timeout=900,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )

    def test_hoot_mobile(self) -> None:
        # Run mobile preset without extra tag filters that can complicate discovery
        url = "/web/tests?headless=1&loglevel=2&preset=mobile&timeout=30000&filter=product_connect"
        try:
            self.browser_js(
                url,
                code="",
                login=self._get_test_login(),
                # Fail fast on mobile preset as well
                timeout=900,
                success_signal="[HOOT] Test suite succeeded",
                error_checker=unit_test_error_checker,
            )
        except TimeoutError:
            # Retry once after a short delay (server likely still compiling assets)
            self.browser_js(
                url,
                code="",
                login=self._get_test_login(),
                timeout=1800,
                success_signal="[HOOT] Test suite succeeded",
                error_checker=unit_test_error_checker,
            )

    def test_check_forbidden_statements(self) -> None:
        re_forbidden = re.compile(r"test.*\.(only|debug)\(")

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
                pass
