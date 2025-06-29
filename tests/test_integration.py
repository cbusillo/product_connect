import os
import glob
from odoo.tests import tagged
from .test_base import ProductConnectHttpCase, ProductConnectIntegrationCase


@tagged("post_install", "-at_install", "product_connect_js")
class TestProductConnectIntegration(ProductConnectHttpCase):
    def test_javascript_tests_run(self) -> None:
        """Test that all JavaScript tests execute properly"""
        # Run all product_connect JavaScript tests
        self.browser_js(
            "/web/tests?headless&loglevel=2&preset=desktop&module=product_connect",
            "",
            login=self.test_user.login,
            timeout=300,
            success_signal="[HOOT] test suite succeeded",
        )


@tagged("post_install", "-at_install", "product_connect_tour")
class TestProductConnectTours(ProductConnectIntegrationCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        # Discover all tour files
        cls.tour_files = []
        tours_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "tests", "tours", "*.js")
        for tour_file in glob.glob(tours_path):
            with open(tour_file) as f:
                content = f.read()
                # Extract tour name from registry.category("web_tour.tours").add("tour_name"
                import re

                match = re.search(r'registry\.category\("web_tour\.tours"\)\.add\("([^"]+)"', content)
                if match:
                    cls.tour_files.append(match.group(1))

    def test_all_tours(self) -> None:
        """Dynamically run all discovered tours"""
        for tour_name in self.tour_files:
            with self.subTest(tour=tour_name):
                try:
                    # Just run the tour - it should handle its own assertions
                    self.start_tour("/odoo", tour_name, login=self.test_user.login, timeout=120)
                except Exception as e:
                    # Tour failed - this is the actual test failure
                    self.fail(f"Tour {tour_name} failed: {str(e)}")
