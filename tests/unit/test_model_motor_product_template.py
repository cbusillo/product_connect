"""Test the motor product template model."""

from odoo import fields
from odoo.exceptions import ValidationError
from ..common_imports import tagged, UNIT_TAGS

from ..fixtures.base import UnitTestCase


@tagged(*UNIT_TAGS)
class TestMotorProductTemplate(UnitTestCase):
    """Test motor product template functionality."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()
        self.MotorProductTemplate = self.env["motor.product.template"]
        self.Motor = self.env["motor"]

        # Create test manufacturer
        self.manufacturer = self.env["product.manufacturer"].create({"name": "Test Manufacturer", "is_motor_manufacturer": True})

        # Create test stroke (needs sudo for ACL)
        self.stroke = self.env["motor.stroke"].sudo().create({"name": "4-Stroke", "code": "4"})

        # Create test configuration (needs sudo for ACL)
        self.configuration = self.env["motor.configuration"].sudo().create({"name": "V6", "code": "V6"})

        # Create test part type
        self.part_type = self.env["product.type"].create({"name": "Test Part Type"})

    def test_year_range_validation(self) -> None:
        """Test that year_from cannot be greater than year_to."""
        with self.assertRaises(ValidationError) as cm:
            self.MotorProductTemplate.create(
                {"name": "Test Template", "year_from": 2020, "year_to": 2010, "part_type": self.part_type.id}
            )
        self.assertIn("cannot be greater than", str(cm.exception))

    def test_year_range_max_validation(self) -> None:
        """Test that year range cannot exceed 100 years."""
        with self.assertRaises(ValidationError) as cm:
            self.MotorProductTemplate.create(
                {"name": "Test Template", "year_from": 1920, "year_to": 2025, "part_type": self.part_type.id}
            )
        self.assertIn("cannot exceed 100 years", str(cm.exception))

    def test_year_range_min_validation(self) -> None:
        """Test that years must be 1900 or later."""
        with self.assertRaises(ValidationError) as cm:
            self.MotorProductTemplate.create({"name": "Test Template", "year_from": 1899, "part_type": self.part_type.id})
        self.assertIn("must be 1900 or later", str(cm.exception))

    def test_year_range_future_validation(self) -> None:
        """Test that years cannot be too far in the future."""
        current_year = fields.Date.today().year
        with self.assertRaises(ValidationError) as cm:
            self.MotorProductTemplate.create({"name": "Test Template", "year_to": current_year + 10, "part_type": self.part_type.id})
        self.assertIn("cannot be more than 5 years in the future", str(cm.exception))

    def test_year_range_display_both_years(self) -> None:
        """Test year range display when both years are set."""
        template = self.MotorProductTemplate.create(
            {"name": "Test Template", "year_from": 2010, "year_to": 2020, "part_type": self.part_type.id}
        )
        self.assertEqual(template.year_range_display, "2010 - 2020")

    def test_year_range_display_only_from(self) -> None:
        """Test year range display when only year_from is set."""
        template = self.MotorProductTemplate.create({"name": "Test Template", "year_from": 2010, "part_type": self.part_type.id})
        self.assertEqual(template.year_range_display, "2010 - Present")

    def test_year_range_display_only_to(self) -> None:
        """Test year range display when only year_to is set."""
        template = self.MotorProductTemplate.create({"name": "Test Template", "year_to": 2020, "part_type": self.part_type.id})
        self.assertEqual(template.year_range_display, "Up to 2020")

    def test_year_range_display_no_years(self) -> None:
        """Test year range display when no years are set."""
        template = self.MotorProductTemplate.create({"name": "Test Template", "part_type": self.part_type.id})
        self.assertEqual(template.year_range_display, "All Years")

    def test_get_motors_for_template_year_filtering(self) -> None:
        """Test that _get_motors_for_template filters by year range."""
        # Create a template with year range
        template = self.MotorProductTemplate.create(
            {
                "name": "Test Template",
                "year_from": 2015,
                "year_to": 2020,
                "part_type": self.part_type.id,
                "strokes": [(6, 0, [self.stroke.id])],
                "configurations": [(6, 0, [self.configuration.id])],
                "manufacturers": [(6, 0, [self.manufacturer.id])],
            }
        )

        # Create motors with different years
        motor_2010 = self.Motor.create(
            {
                "motor_number": "M-000001",
                "year": "2010",
                "horsepower": 100,
                "stroke": self.stroke.id,
                "configuration": self.configuration.id,
                "manufacturer": self.manufacturer.id,
                "currency_id": self.env.ref("base.USD").id,
                "model": "Test Model 2010",
            }
        )

        motor_2015 = self.Motor.create(
            {
                "motor_number": "M-000002",
                "year": "2015",
                "horsepower": 100,
                "stroke": self.stroke.id,
                "configuration": self.configuration.id,
                "manufacturer": self.manufacturer.id,
                "currency_id": self.env.ref("base.USD").id,
                "model": "Test Model 2015",
            }
        )

        motor_2018 = self.Motor.create(
            {
                "motor_number": "M-000003",
                "year": "2018",
                "horsepower": 100,
                "stroke": self.stroke.id,
                "configuration": self.configuration.id,
                "manufacturer": self.manufacturer.id,
                "currency_id": self.env.ref("base.USD").id,
                "model": "Test Model 2018",
            }
        )

        motor_2025 = self.Motor.create(
            {
                "motor_number": "M-000004",
                "year": "2025",
                "horsepower": 100,
                "stroke": self.stroke.id,
                "configuration": self.configuration.id,
                "manufacturer": self.manufacturer.id,
                "currency_id": self.env.ref("base.USD").id,
                "model": "Test Model 2025",
            }
        )

        # Get motors for template
        matching_motors = template._get_motors_for_template()

        # Should only include motors from 2015-2020
        self.assertIn(motor_2015, matching_motors)
        self.assertIn(motor_2018, matching_motors)
        self.assertNotIn(motor_2010, matching_motors)
        self.assertNotIn(motor_2025, matching_motors)

    def test_get_motors_for_template_no_year_range(self) -> None:
        """Test that templates without year range match all motors."""
        # Create a template without year range
        template = self.MotorProductTemplate.create(
            {
                "name": "Test Template",
                "part_type": self.part_type.id,
                "strokes": [(6, 0, [self.stroke.id])],
                "configurations": [(6, 0, [self.configuration.id])],
                "manufacturers": [(6, 0, [self.manufacturer.id])],
            }
        )

        # Create motors with different years
        motor_2010 = self.Motor.create(
            {
                "motor_number": "M-000005",
                "year": "2010",
                "horsepower": 100,
                "stroke": self.stroke.id,
                "configuration": self.configuration.id,
                "manufacturer": self.manufacturer.id,
                "currency_id": self.env.ref("base.USD").id,
                "model": "Test Model",
            }
        )

        motor_2025 = self.Motor.create(
            {
                "motor_number": "M-000006",
                "year": "2025",
                "horsepower": 100,
                "stroke": self.stroke.id,
                "configuration": self.configuration.id,
                "manufacturer": self.manufacturer.id,
                "currency_id": self.env.ref("base.USD").id,
                "model": "Test Model",
            }
        )

        # Get motors for template
        matching_motors = template._get_motors_for_template()

        # Should include all motors
        self.assertIn(motor_2010, matching_motors)
        self.assertIn(motor_2025, matching_motors)
