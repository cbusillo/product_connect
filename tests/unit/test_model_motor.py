import base64

from ..common_imports import tagged, ValidationError, UNIT_TAGS
from ..fixtures.base import UnitTestCase
from ..fixtures.factories import MotorFactory


@tagged(*UNIT_TAGS)
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
        result = self.env["motor"]._sanitize_vals({"model": "abc", "serial_number": "sn1"})
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

    def test_create_motor_products_year_filtering(self) -> None:
        """Test that create_motor_products respects year range filtering."""
        # Create motors with different years
        motor_2010 = self._create_test_motor(year=2010, cost=100.0)
        motor_2018 = self._create_test_motor(year=2018, cost=100.0)
        motor_2025 = self._create_test_motor(year=2025, cost=100.0)
        
        # Create a motor product template with year range 2015-2020
        template = self.env["motor.product.template"].create({
            "name": "Year-Specific Part",
            "year_from": 2015,
            "year_to": 2020,
            "strokes": [(6, 0, [motor_2018.stroke.id])],
            "configurations": [(6, 0, [motor_2018.configuration.id])],
            "manufacturers": [(6, 0, [motor_2018.manufacturer.id])],
            "initial_quantity": 1,
            "part_type": self.env["product.type"].create({"name": "Test Type"}).id
        })
        
        # Create products for all motors
        (motor_2010 | motor_2018 | motor_2025).create_motor_products()
        
        # Check that only the 2018 motor has the product
        self.assertEqual(len(motor_2010.products), 0, "Motor from 2010 should not have products (before year range)")
        self.assertEqual(len(motor_2018.products), 1, "Motor from 2018 should have 1 product (within year range)")
        self.assertEqual(motor_2018.products[0].motor_product_template, template)
        self.assertEqual(len(motor_2025.products), 0, "Motor from 2025 should not have products (after year range)")

    def test_create_motor_products_no_year_range(self) -> None:
        """Test that templates without year range apply to all motors."""
        # Create motors with different years
        motor_2010 = self._create_test_motor(year=2010, cost=100.0)
        motor_2025 = self._create_test_motor(year=2025, cost=100.0)
        
        # Create a motor product template without year range
        template = self.env["motor.product.template"].create({
            "name": "Universal Part",
            # No year_from or year_to
            "strokes": [(6, 0, [motor_2010.stroke.id])],
            "configurations": [(6, 0, [motor_2010.configuration.id])],
            "manufacturers": [(6, 0, [motor_2010.manufacturer.id])],
            "initial_quantity": 1,
            "part_type": self.env["product.type"].create({"name": "Test Type"}).id
        })
        
        # Create products for all motors
        (motor_2010 | motor_2025).create_motor_products()
        
        # Check that both motors have the product
        self.assertEqual(len(motor_2010.products), 1, "Motor from 2010 should have the universal product")
        self.assertEqual(motor_2010.products[0].motor_product_template, template)
        self.assertEqual(len(motor_2025.products), 1, "Motor from 2025 should have the universal product")
        self.assertEqual(motor_2025.products[0].motor_product_template, template)

    def test_create_motor_product_generation(self) -> None:
        """Test motor product creation using factory."""
        # Create motor using factory
        motor = MotorFactory.create(self.env)

        # Verify motor was created with correct attributes
        self.assertTrue(motor)
        self.assertGreater(motor.horsepower, 0)
        self.assertTrue(motor.model)
        self.assertTrue(motor.serial_number)

        # Test with custom values
        custom_motor = MotorFactory.create(
            self.env,
            horsepower=150,
            year=2023,
            model="CUSTOM-MODEL"
        )
        self.assertEqual(custom_motor.horsepower, 150)
        self.assertEqual(custom_motor.year, 2023)
        self.assertEqual(custom_motor.model, "CUSTOM-MODEL")

    def test_motor_factory_creation(self) -> None:
        """Test that motor factory creates motors with unique identifiers."""
        # Create multiple motors using factory
        motor1 = MotorFactory.create(self.env, horsepower=100)
        motor2 = MotorFactory.create(self.env, horsepower=120)

        # Verify motors are unique
        self.assertNotEqual(motor1.id, motor2.id)
        self.assertNotEqual(motor1.motor_number, motor2.motor_number)
        self.assertNotEqual(motor1.serial_number, motor2.serial_number)

        # Verify both have correct properties
        self.assertEqual(motor1.horsepower, 100)
        self.assertEqual(motor2.horsepower, 120)
        self.assertTrue(motor1.model)
        self.assertTrue(motor2.model)
