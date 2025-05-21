from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class TestMotor(TransactionCase):
    test_tags = {"-at_install", "-post_install"}

    def setUp(self) -> None:
        super().setUp()
        self.stage = self.env["motor.stage"].create({"name": "Checkin"})
        self.manufacturer = self.env["product.manufacturer"].create({"name": "Maker", "is_motor_manufacturer": True})
        self.stroke = self.env["motor.stroke"].create({"name": "Four", "code": "4"})
        self.config = self.env["motor.configuration"].create({"name": "I4", "code": "4"})

    def _create_motor(self, **extra: object) -> "odoo.model.motor":
        vals: dict[str, object] = {
            "manufacturer": self.manufacturer.id,
            "stroke": self.stroke.id,
            "configuration": self.config.id,
            "horsepower": 90.0,
        }
        vals.update(extra)
        return self.env["motor"].create(vals)

    def test_get_horsepower_formatted(self) -> None:
        motor = self._create_motor(horsepower=100.0)
        self.assertEqual(motor.get_horsepower_formatted(), "100 HP")
        motor.horsepower = 100.5
        self.assertEqual(motor.get_horsepower_formatted(), "100.5 HP")

    def test_sanitize_vals(self) -> None:
        result = self.env["motor"]._sanitize_vals({"year": "2020a", "model": "abc", "serial_number": "sn1"})
        self.assertEqual(result["year"], "2020")
        self.assertEqual(result["model"], "ABC")
        self.assertEqual(result["serial_number"], "SN1")

    def test_unique_location(self) -> None:
        self._create_motor(location="A1")
        with self.assertRaises(ValidationError):
            self._create_motor(location="A1")

    def test_generate_qr_code(self) -> None:
        motor = self._create_motor()
        code = motor.generate_qr_code()
        self.assertTrue(code)
        import base64

        base64.b64decode(code)
