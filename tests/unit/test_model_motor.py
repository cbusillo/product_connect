import base64

from odoo.tests import tagged
from ..fixtures.base import UnitTestCase
from ..fixtures.factories import MotorFactory
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "unit_test")
class TestMotor(UnitTestCase):
    def setUp(self) -> None:
        super().setUp()
        # Create motor dependencies using factory
        self.stage = self.env["motor.stage"].create({"name": "Checkin"})
        self.test_motor = MotorFactory.create(self.env)

    def _create_test_motor(self, **extra: int | float | str) -> "odoo.model.motor":
        return MotorFactory.create(self.env, **extra)

    def test_get_horsepower_formatted(self) -> None:
        motor = self._create_test_motor(horsepower=100.0)
        self.assertEqual(motor.get_horsepower_formatted(), "100 HP")
        motor.horsepower = 100.5
        self.assertEqual(motor.get_horsepower_formatted(), "100.5 HP")

    def test_sanitize_vals(self) -> None:
        result = self.env["motor"]._sanitize_vals({"year": "2020a", "model": "abc", "serial_number": "sn1"})
        self.assertEqual(result["year"], "2020")
        self.assertEqual(result["model"], "ABC")
        self.assertEqual(result["serial_number"], "SN1")

    def test_unique_location(self) -> None:
        self._create_test_motor(location="A1")
        with self.assertRaises(ValidationError):
            self._create_test_motor(location="A1")

    def test_generate_qr_code(self) -> None:
        motor = self._create_test_motor()
        code = motor.generate_qr_code()
        self.assertTrue(code)
        base64.b64decode(code)

    def test_create_motor_dependencies(self) -> None:
        """Test motor creation with proper dependencies."""
        # Create motor using factory
        motor = MotorFactory.create(self.env)

        # Verify motor was created with dependencies
        self.assertTrue(motor.manufacturer)
        self.assertTrue(motor.stroke)
        self.assertTrue(motor.configuration)

        # Verify motor has expected properties
        self.assertGreater(motor.horsepower, 0)
        self.assertTrue(motor.motor_year)
        self.assertTrue(motor.motor_model)
        self.assertTrue(motor.motor_serial)

    def test_create_motor_product_generation(self) -> None:
        """Test motor product creation using factory."""
        # Create motor using factory
        motor = MotorFactory.create(self.env)

        # Verify motor was created with correct attributes
        self.assertTrue(motor)
        self.assertGreater(motor.motor_hp, 0)
        self.assertTrue(motor.motor_model)
        self.assertTrue(motor.motor_serial)

        # Test with custom values
        custom_motor = MotorFactory.create(
            self.env,
            motor_hp=150,
            motor_year=2023,
            motor_model="CUSTOM-MODEL"
        )
        self.assertEqual(custom_motor.motor_hp, 150)
        self.assertEqual(custom_motor.motor_year, 2023)
        self.assertEqual(custom_motor.motor_model, "CUSTOM-MODEL")

    def test_motor_factory_creation(self) -> None:
        """Test that motor factory creates motors with unique identifiers."""
        # Create multiple motors using factory
        motor1 = MotorFactory.create(self.env, motor_hp=100)
        motor2 = MotorFactory.create(self.env, motor_hp=120)

        # Verify motors are unique
        self.assertNotEqual(motor1.id, motor2.id)
        self.assertNotEqual(motor1.default_code, motor2.default_code)
        self.assertNotEqual(motor1.motor_serial, motor2.motor_serial)

        # Verify both have correct properties
        self.assertEqual(motor1.motor_hp, 100)
        self.assertEqual(motor2.motor_hp, 120)
        self.assertTrue(motor1.motor_model)
        self.assertTrue(motor2.motor_model)
