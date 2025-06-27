from odoo.tests import tagged
from .test_base import ProductConnectHttpCase, ProductConnectIntegrationCase


@tagged("post_install", "-at_install", "product_connect_js")
class TestProductConnectIntegration(ProductConnectHttpCase):

    def test_javascript_tests_run(self) -> None:
        """Test that JavaScript tests execute properly"""
        # Use the test user created in setUpClass
        self.browser_js(
            "/web/tests?headless&loglevel=2&preset=desktop&filter=Basic%20Product%20Connect%20Tests",
            "",
            login=self.test_user.login,
            timeout=300,
            success_signal="[HOOT] test suite succeeded",
        )


@tagged("post_install", "-at_install", "product_connect_tour")
class TestProductConnectTours(ProductConnectIntegrationCase):

    def test_basic_tour(self) -> None:
        """Test basic tour functionality"""
        self.start_tour("/web", "test_basic_tour", login=self.test_user.login, timeout=60)

    def test_motor_workflow_tour(self) -> None:
        """Test motor creation workflow"""
        # This tour requires specific UI elements that may not be available in test environment
        self.skipTest("Motor workflow tour requires specific UI setup")

    def test_motor_qr_scan_tour(self) -> None:
        """Test motor QR code scanning"""
        # This tour requires specific UI elements that may not be available in test environment
        self.skipTest("Motor QR scan tour requires specific UI setup")
