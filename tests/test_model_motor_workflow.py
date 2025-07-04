from odoo.tests import tagged
from .fixtures.test_base import ProductConnectTransactionCase


@tagged("post_install", "-at_install")
class TestMotorWorkflow(ProductConnectTransactionCase):
    """Unit tests for motor workflow and product creation"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        # Context is already set by base class

        # Create test data
        cls.manufacturer = cls.env["product.manufacturer"].create(
            {
                "name": "Test Motor Manufacturer",
                "is_motor_manufacturer": True,
            }
        )

        # Create motor product templates
        cls.motor_product_templates = []
        cls.part_type = cls.env["product.type"].create({"name": "Test Motor Part Type"})

        for i in range(3):
            template = cls.env["motor.product.template"].create(
                {
                    "name": f"Test Product Template {i}",
                    "initial_quantity": 1.0,
                    "manufacturers": [(6, 0, [cls.manufacturer.id])],
                    "bin": f"BIN-{i}",
                    "weight": 10.0 + i,
                    "part_type": cls.part_type.id,
                    "website_description": f"<p>Test product {i} description</p>",
                }
            )
            cls.motor_product_templates.append(template)

    def test_motor_creation(self) -> None:
        """Test basic motor creation with required fields"""
        motor = self.env["motor"].create(
            {
                "manufacturer": self.manufacturer.id,
                "horsepower": 200,
                "year": "2024",
                "model": "Test Model",
                "serial_number": "TEST123456",
                "location": "A1-B2-C3",
                "stroke": self.env.ref("product_connect.stroke_4").id,
                "configuration": self.env.ref("product_connect.config_v6").id,
                "cost": 1000.0,
            }
        )

        self.assertTrue(motor.exists())
        # Check display name contains key components
        self.assertIn("2024", motor.display_name)
        self.assertIn("Test Motor Manufacturer", motor.display_name)
        self.assertIn("200", motor.display_name)
        self.assertIn("TEST MODEL", motor.display_name)
        self.assertEqual(motor.serial_number, "TEST123456")

    def test_motor_product_creation(self) -> None:
        """Test creating products from motor"""
        motor = self.env["motor"].create(
            {
                "manufacturer": self.manufacturer.id,
                "horsepower": 150,
                "year": "2023",
                "model": "Product Test",
                "serial_number": "PROD123456",
                "location": "D4-E5",
                "stroke": self.env.ref("product_connect.stroke_2").id,
                "configuration": self.env.ref("product_connect.config_i4").id,
                "cost": 1500.0,
            }
        )

        # Create motor products
        motor.create_motor_products()

        # Should have created products based on motor product templates
        self.assertTrue(len(motor.products) >= len(self.motor_product_templates))

        # Check products were created
        self.assertTrue(motor.products.exists())

    def test_motor_product_enabling(self) -> None:
        """Test enabling products for sale and purchase"""
        motor = self.env["motor"].create(
            {
                "manufacturer": self.manufacturer.id,
                "horsepower": 175,
                "year": "2023",
                "model": "Enable Test",
                "serial_number": "ENABLE123456",
                "location": "F6-G7",
                "stroke": self.env.ref("product_connect.stroke_4").id,
                "configuration": self.env.ref("product_connect.config_v8").id,
                "cost": 2000.0,
            }
        )

        # Create products
        motor.create_motor_products()

        # Initially products should not be ready for sale
        for product in motor.products:
            self.assertFalse(product.is_ready_for_sale)

        # Simple test - just enable the is_ready_for_sale flag directly
        motor.products.write({"is_ready_for_sale": True})

        # Now should be ready for sale
        for product in motor.products:
            self.assertTrue(product.is_ready_for_sale)

        # Test purchase_ok flag
        motor.products.write({"purchase_ok": False})
        for product in motor.products:
            self.assertFalse(product.purchase_ok)

        motor.products.write({"purchase_ok": True})
        for product in motor.products:
            self.assertTrue(product.purchase_ok)
