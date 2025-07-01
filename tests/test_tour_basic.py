from odoo.tests import HttpCase, tagged
import secrets


@tagged("post_install", "-at_install", "product_connect_tour")
class TestBasicTour(HttpCase):
    """Template tour test runner

    Tour tests should be organized as:
    1. Tour definition: static/tests/tours/feature_name_tour.js
    2. Tour runner: tests/tours/test_feature_name_tour.py (this file)

    This separation ensures tours are discovered and executed properly.
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        # Skip external services during tests
        cls.env = cls.env(context=dict(cls.env.context, skip_shopify_sync=True))

        # Create test user with secure password
        secure_password = secrets.token_urlsafe(32)
        cls.test_user = cls.env["res.users"].create(
            {
                "name": "Basic Tour User",
                "login": "basic_tour_user",
                "password": secure_password,
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                        ],
                    )
                ],
            }
        )
        cls.test_user_password = secure_password

        # Create any test data needed for the tour
        cls._setup_tour_data()

    @classmethod
    def _setup_tour_data(cls) -> None:
        """Set up data needed for the tour"""
        # Example: Create test records that the tour will interact with
        pass

    def test_basic_tour(self) -> None:
        """
        Run the basic tour that tests:
        - Odoo UI loads correctly
        - Main navbar exists
        - Apps menu is accessible

        The actual tour steps are defined in:
        static/tests/tours/basic_tour.js
        """
        self.start_tour(
            "/odoo",
            "test_basic_tour",  # Must match the tour name in basic_tour.js
            login=self.test_user.login,
            timeout=60,
        )
