from odoo import SUPERUSER_ID
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestMotorFrontendTour(HttpCase):
    _password = "tour_password8glue34ji"
    _login = "tour_admin"

    def setUp(self) -> None:
        super().setUp()

        test_admin = self.env.ref("base.group_system")
        self.tour_user = (
            self.env["res.users"]
            .with_user(SUPERUSER_ID)
            .create(
                {
                    "name": "Tour Administrator",
                    "login": self._login,
                    "password": self._password,
                    "groups_id": [(6, 0, [test_admin.id])],
                }
            )
        )

    def test_motor_frontend_tour(self) -> None:
        self.start_tour(
            "/web",
            "motor_frontend_tour",
            login=self._login,
            password=self._password,
            modules="product_connect",
        )
