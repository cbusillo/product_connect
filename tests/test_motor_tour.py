from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestMotorFrontendTour(HttpCase):
    def test_motor_frontend_tour(self) -> None:
        self.start_tour("/web", "motor_frontend_tour", login="admin")
