import odoo.tests
from odoo.tests import tagged


@tagged("post_install", "-at_install", "product_connect_js")
class TestProductConnectIntegration(odoo.tests.HttpCase):
    def test_javascript_tests_run(self) -> None:
        """Test that JavaScript tests execute properly"""
        self.browser_js(
            "/web/tests?headless&loglevel=2&preset=desktop&filter=Basic%20Product%20Connect%20Tests",
            "",
            login="admin",
            timeout=300,
            success_signal="[HOOT] test suite succeeded",
        )


@tagged("post_install", "-at_install", "product_connect_tour")
class TestProductConnectTours(odoo.tests.HttpCase):
    def test_motor_workflow_tour(self) -> None:
        """Test motor creation workflow"""
        self.start_tour("/web", "motor_workflow_tour", login="admin", timeout=180)

    def test_motor_qr_scan_tour(self) -> None:
        """Test motor QR code scanning"""
        self.start_tour("/web", "motor_qr_scan_tour", login="admin", timeout=180)
