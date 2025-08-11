from odoo.tests import tagged
from ..fixtures.base import UnitTestCase
from ..fixtures.factories import MotorFactory, ProductFactory, PartnerFactory


@tagged("post_install", "-at_install", "unit_test")
class TestMotorWorkflow(UnitTestCase):
    """Unit tests for motor workflow and product creation"""

    def setUp(self) -> None:
        super().setUp()
        # Unit tests create their own minimal data as needed

    def test_motor_creation(self) -> None:
        """Test basic motor creation with required fields"""
        motor = MotorFactory.create(
            self.env,
            motor_hp=200,
            motor_year=2024,
            motor_model="Test Model"
        )

        self.assertTrue(motor.exists())
        self.assertEqual(motor.motor_hp, 200)
        self.assertEqual(motor.motor_year, 2024)
        self.assertEqual(motor.motor_model, "Test Model")
        self.assertTrue(motor.motor_serial)

    def test_motor_product_creation(self) -> None:
        """Test creating motor as product template"""
        motor = MotorFactory.create(
            self.env,
            motor_hp=150,
            motor_year=2023,
            motor_model="Product Test"
        )

        # Verify motor was created as a product template
        self.assertTrue(motor.exists())
        self.assertEqual(motor.type, "product")  # Motors are typically 'product' type
        self.assertGreater(motor.list_price, 0)  # Should have a price
        self.assertTrue(motor.default_code)  # Should have SKU

    def test_motor_product_enabling(self) -> None:
        """Test enabling motor products for sale and purchase"""
        motor = MotorFactory.create(
            self.env,
            motor_hp=175,
            motor_year=2023,
            motor_model="Enable Test"
        )

        # Test basic product flags - motors should be sellable/purchasable by default from factory
        self.assertTrue(motor.sale_ok)
        self.assertTrue(motor.purchase_ok)

        # Test toggling sale flag
        motor.write({"sale_ok": False})
        self.assertFalse(motor.sale_ok)

        motor.write({"sale_ok": True})
        self.assertTrue(motor.sale_ok)

        # Test toggling purchase flag
        motor.write({"purchase_ok": False})
        self.assertFalse(motor.purchase_ok)

        motor.write({"purchase_ok": True})
        self.assertTrue(motor.purchase_ok)
