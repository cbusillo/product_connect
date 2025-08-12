
import secrets

from ..common_imports import tagged, ValidationError, UNIT_TAGS
from ..fixtures.base import UnitTestCase
from ..fixtures.factories import ProductFactory, MotorFactory


@tagged(*UNIT_TAGS)
class TestProductTemplate(UnitTestCase):
    def setUp(self) -> None:
        super().setUp()
        # Context is already set by UnitTestCase base class

    def _assert_sku_validation_error(self, invalid_skus: list[str]) -> None:
        for sku in invalid_skus:
            with self.subTest(sku=sku):
                with self.assertRaises(ValidationError) as context:
                    self.env["product.template"].create({"name": f"Test Product {sku}", "default_code": sku, "type": "consu"})
                self.assertIn("SKU must be 4-8 digits", str(context.exception))

    def test_product_creation_basic(self) -> None:
        """Test basic product creation using factory"""
        product = ProductFactory.create(
            self.env,
            name="Test Product",
            type="consu"
        )
        
        self.assertTrue(product.exists())
        self.assertEqual(product.type, "consu")
        self.assertTrue(product.default_code)  # Factory should generate SKU
        self.assertGreater(product.list_price, 0)  # Factory sets price

    def test_sku_validation_valid_numeric_skus(self) -> None:
        # Generate unique valid SKUs to avoid database constraint violations
        valid_sku_patterns = [4, 5, 6, 7, 8]  # Different valid lengths
        for length in valid_sku_patterns:
            # Generate unique SKU with specified length, avoiding conflicts with base class SKUs
            base_num = secrets.randbelow(10**(length-1))  # Ensure we don't exceed the length
            unique_sku = f"{base_num:0{length}d}"  # Zero-pad to specified length
            
            with self.subTest(sku=unique_sku):
                product = self.env["product.template"].create({"name": f"Test Product {unique_sku}", "default_code": unique_sku, "type": "consu"})
                self.assertEqual(product.default_code, unique_sku)
                product.unlink()

    def test_sku_validation_invalid_alphanumeric_skus(self) -> None:
        invalid_skus = ["PROD-A", "TEST-SKU-001", "ABC123", "SKU123", "123ABC"]
        self._assert_sku_validation_error(invalid_skus)

    def test_sku_validation_invalid_length_skus(self) -> None:
        invalid_skus = ["123", "123456789", "12", "1"]
        self._assert_sku_validation_error(invalid_skus)

    def test_sku_validation_skip_for_non_consumable_products(self) -> None:
        invalid_sku = "INVALID-SKU"
        product = self.env["product.template"].create({"name": "Test Service", "default_code": invalid_sku, "type": "service"})
        self.assertEqual(product.default_code, invalid_sku)

    def test_sku_validation_bypass_with_context(self) -> None:
        invalid_sku = "INVALID-SKU"
        product = (
            self.env["product.template"]
            .with_context(skip_sku_check=True)
            .create({"name": "Test Bypass", "default_code": invalid_sku, "type": "consu"})
        )
        self.assertEqual(product.default_code, invalid_sku)

    def test_sku_validation_boundary_4_digit(self) -> None:
        """Test exact 4-digit boundary cases"""
        # Valid 4-digit boundaries
        valid_skus = ["1000", "9999"]
        for sku in valid_skus:
            with self.subTest(sku=sku):
                product = self.env["product.template"].create({"name": f"Test Product {sku}", "default_code": sku, "type": "consu"})
                self.assertEqual(product.default_code, sku)
                product.unlink()

        # Invalid boundary cases
        invalid_skus = ["0999", "999"]
        self._assert_sku_validation_error(invalid_skus)

    def test_sku_validation_boundary_8_digit(self) -> None:
        """Test exact 8-digit boundary cases"""
        # Valid 8-digit boundaries
        valid_skus = ["10000000", "99999999"]
        for sku in valid_skus:
            with self.subTest(sku=sku):
                product = self.env["product.template"].create({"name": f"Test Product {sku}", "default_code": sku, "type": "consu"})
                self.assertEqual(product.default_code, sku)
                product.unlink()

        # Invalid boundary case - 9 digits
        invalid_skus = ["100000000"]
        self._assert_sku_validation_error(invalid_skus)

    def test_sku_validation_edge_cases(self) -> None:
        """Test edge cases for SKU validation"""
        # Test empty string - should auto-generate SKU for consumable products
        product = self.env["product.template"].create({"name": "Test Empty SKU", "default_code": "", "type": "consu"})
        self.assertIsNotNone(product.default_code, "Empty SKU should auto-generate for consumable products")
        self.assertNotEqual(product.default_code, "", "Auto-generated SKU should not be empty")
        # Verify the auto-generated SKU matches the pattern
        self.assertRegex(product.default_code, r'^\d{4,8}$', "Auto-generated SKU should match pattern")
        product.unlink()

        # Test None value - should also auto-generate SKU for consumable products
        product = self.env["product.template"].create({"name": "Test None SKU", "default_code": None, "type": "consu"})
        self.assertIsNotNone(product.default_code, "None SKU should auto-generate for consumable products")
        self.assertRegex(product.default_code, r'^\d{4,8}$', "Auto-generated SKU should match pattern")
        product.unlink()

        # Test whitespace (should fail validation because whitespace isn't stripped)
        unique_sku_with_spaces = f"  {secrets.randbelow(9000) + 1000}  "  # e.g., "  1234  "
        with self.assertRaises(ValidationError) as context:
            self.env["product.template"].create({"name": "Test Whitespace SKU", "default_code": unique_sku_with_spaces, "type": "consu"})
        self.assertIn("SKU must be 4-8 digits", str(context.exception))

        # Test leading zeros (should be treated as string, not number)
        unique_sku_with_zeros = f"000{secrets.randbelow(9000) + 1000}"  # e.g., "00001234"
        product = self.env["product.template"].create({"name": "Test Leading Zeros", "default_code": unique_sku_with_zeros, "type": "consu"})
        self.assertEqual(product.default_code, unique_sku_with_zeros)
        product.unlink()

    def test_is_scrap_field_default_value(self) -> None:
        """Test that is_scrap field defaults to False"""
        unique_sku = f"{secrets.randbelow(90000000) + 10000000}"  # Generate unique 8-digit SKU
        product = self.env["product.template"].create({"name": "Test Scrap Product", "default_code": unique_sku, "type": "consu"})
        self.assertFalse(product.is_scrap, "is_scrap should default to False")

    def test_is_scrap_field_can_be_set(self) -> None:
        """Test that is_scrap field can be set to True"""
        unique_sku = f"{secrets.randbelow(90000000) + 10000000}"  # Generate unique 8-digit SKU
        product = self.env["product.template"].create({"name": "Test Scrap Product", "default_code": unique_sku, "type": "consu"})
        product.is_scrap = True
        self.assertTrue(product.is_scrap, "is_scrap should be True after setting")

    def test_motor_product_creation(self) -> None:
        """Test that motor products can be created with basic properties"""
        product = MotorFactory.create(
            self.env,
            name="Test Motor Product",
            motor_hp=100
        )
        
        self.assertTrue(product.exists())
        # Access motor fields through the linked motor record
        self.assertEqual(product.motor.horsepower, 100)
        self.assertTrue(product.motor.serial_number)
        self.assertTrue(product.default_code)

    def test_product_scrap_field_basic(self) -> None:
        """Test basic scrap field functionality"""
        product = ProductFactory.create(
            self.env,
            name="Test Scrap Product",
            type="consu"
        )
        
        # Test default value
        if hasattr(product, 'is_scrap'):
            self.assertFalse(product.is_scrap, "is_scrap should default to False")
            
            # Test setting scrap flag
            product.is_scrap = True
            self.assertTrue(product.is_scrap, "is_scrap should be True after setting")
        else:
            # Skip test if is_scrap field doesn't exist
            self.skipTest("is_scrap field not available in current model")





    def test_name_field_validation(self) -> None:
        """Test that name field behavior matches Odoo's actual validation"""
        # Test that empty name is allowed (Odoo only requires NOT NULL, empty string is valid)
        unique_sku = f"99{secrets.randbelow(999999):06d}"
        product = self.env["product.template"].create({"name": "", "default_code": unique_sku, "type": "consu"})
        self.assertEqual(product.name, "", "Empty string name should be allowed")
        product.unlink()

        # Test that name field accepts valid values - use another unique SKU
        valid_sku = f"88{secrets.randbelow(999999):06d}"
        product = self.env["product.template"].create({"name": "Test Product Name", "default_code": valid_sku, "type": "consu"})
        self.assertEqual(product.name, "Test Product Name")

        # Test that name can be updated
        product.name = "Updated Product Name"
        self.assertEqual(product.name, "Updated Product Name")

        # Test that name can be set to empty string after creation (Odoo allows this)
        product.name = ""
        self.assertEqual(product.name, "", "Setting name to empty string should be allowed")
        
        # Test that None name raises database constraint error during creation
        with self.assertRaises(Exception) as context:
            self.env["product.template"].create({"default_code": f"77{secrets.randbelow(999999):06d}", "type": "consu"})
        # Should be a database constraint error about null values
        self.assertIn("null value", str(context.exception).lower())
