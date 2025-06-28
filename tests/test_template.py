from odoo.tests import TransactionCase, HttpCase, tagged
from unittest.mock import patch, MagicMock
from odoo.exceptions import ValidationError
import secrets


@tagged("post_install", "-at_install", "test_template")
class TestTemplate(TransactionCase):
    """Template test demonstrating best practices with res.partner model"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        # Skip external services and tracking during tests
        cls.env = cls.env(context=dict(cls.env.context, skip_shopify_sync=True, tracking_disable=True))

        # Create test data
        cls._create_test_data()

    @classmethod
    def _create_test_data(cls) -> None:
        """Create test data"""
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Template Test Partner",
                "email": "template.test@example.com",
                "phone": "+1234567890",
            }
        )

        cls.company = cls.env["res.company"].create(
            {
                "name": "Template Test Company",
                "email": "company@example.com",
            }
        )

        # User for testing permissions
        cls.test_user = cls.env["res.users"].create(
            {
                "name": "Template Test User",
                "login": "template_user",
                "email": "user@example.com",
                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

    def setUp(self) -> None:
        """Set up test-specific data"""
        super().setUp()
        # Example: Create test-specific data that varies per test
        self.test_timestamp = f"test_{self.id()}"

    def test_partner_creation(self) -> None:
        """Test partner creation and field values"""
        self.assertEqual(self.partner.name, "Template Test Partner")
        self.assertEqual(self.partner.email, "template.test@example.com")
        self.assertTrue(self.partner.is_company is False)

    def test_validation_error(self) -> None:
        """Test validation error handling"""
        # Partner name is required
        with self.assertRaises(Exception):
            self.env["res.partner"].create(
                {
                    "name": False,
                    "email": "invalid@example.com",
                }
            )

    def test_context_usage(self) -> None:
        """Test using context to control behavior"""
        # Example: Skip some processing with context
        partner_with_context = (
            self.env["res.partner"]
            .with_context(skip_validation=True)
            .create(
                {
                    "name": "Context Test Partner",
                    "email": "context@example.com",
                }
            )
        )
        self.assertTrue(partner_with_context.exists())

        # Check context is available
        self.assertTrue(self.env.context.get("skip_shopify_sync", False))

    def test_partner_search(self) -> None:
        """Test partner search functionality"""
        found_partners = self.env["res.partner"].search([("name", "=", "Template Test Partner")])
        self.assertIn(self.partner, found_partners)
        self.assertGreaterEqual(len(found_partners), 1)

    def test_with_patch_object_context_manager(self) -> None:
        """Example using patch.object as context manager"""
        # Mock a method on res.partner model
        with patch.object(type(self.partner), "message_post") as mock_message_post:
            mock_message_post.return_value = True

            # Call method that would post a message
            self.partner.message_post(body="Test message", subject="Test")

            # Verify mock was called correctly
            mock_message_post.assert_called_once_with(body="Test message", subject="Test")

    @patch.object(ValidationError, "__init__", return_value=None)
    def test_with_patch_object_decorator(self, mock_init: MagicMock) -> None:
        """Example using patch.object as decorator"""
        # This is a contrived example - normally you'd mock actual business logic
        try:
            # Code that might raise ValidationError
            if not self.partner.email:
                raise ValidationError("Email required")
        except ValidationError:
            # Mock prevents the actual exception
            pass

        # In real tests, mock external services or complex computations
        self.assertTrue(mock_init.called or not mock_init.called)  # Always true


@tagged("post_install", "-at_install", "test_template_tour")
class TestTemplateUI(HttpCase):
    """Template for UI/Browser tests using res.partner"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.env = cls.env(context=dict(cls.env.context, skip_shopify_sync=True, tracking_disable=True))

        # Create test user with secure password
        secure_password = secrets.token_urlsafe(32)
        cls.test_user = cls.env["res.users"].create(
            {
                "name": "Template Test User",
                "login": "template_test_user",
                "password": secure_password,
                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.test_user_password = secure_password

        # Create test data
        cls._create_test_data()

    @classmethod
    def _create_test_data(cls) -> None:
        """Create test data for UI tests"""
        cls.test_partner = cls.env["res.partner"].create(
            {
                "name": "UI Test Partner",
                "email": "ui.test@example.com",
            }
        )

    def test_ui_partner_access(self) -> None:
        """Test UI access to partner"""
        self.assertTrue(self.test_user.exists())
        self.assertTrue(self.test_partner.exists())

    def test_browser_js_example(self) -> None:
        """Example browser JS test"""
        # Skip browser test in template to avoid errors
        self.skipTest("Template browser test - implement for actual feature")
