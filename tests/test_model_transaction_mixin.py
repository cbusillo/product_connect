from unittest.mock import patch

from odoo.tests import tagged

from .fixtures.test_base import ProductConnectTransactionCase


@tagged("post_install", "-at_install")
class TestTransactionMixin(ProductConnectTransactionCase):
    def setUp(self) -> None:
        super().setUp()
        # Create a test model that uses the transaction mixin
        self.test_model = self.env["shopify.sync"]

    def test_safe_commit_in_test_mode(self) -> None:
        """Verify _safe_commit() doesn't actually commit in test mode"""
        with patch.object(self.test_model.env.cr, "commit") as mock_commit:
            # This should not commit because we're in test mode
            self.test_model._safe_commit()
            mock_commit.assert_not_called()

    def test_safe_rollback_in_test_mode(self) -> None:
        """Verify _safe_rollback() doesn't actually rollback in test mode"""
        with patch.object(self.test_model.env.cr, "rollback") as mock_rollback:
            # This should not rollback because we're in test mode
            self.test_model._safe_rollback()
            mock_rollback.assert_not_called()

    def test_safe_commit_outside_test_mode(self) -> None:
        """Verify _safe_commit() actually commits outside test mode"""
        from odoo.tools import config

        # Need to patch both detection methods
        with patch.object(self.test_model.env.registry, "in_test_mode", return_value=False):
            with patch.object(config, "get", return_value=False):
                with patch.object(self.test_model.env.cr, "commit") as mock_commit:
                    # This should commit because all test detections return False
                    self.test_model._safe_commit()
                    mock_commit.assert_called_once()

    def test_safe_rollback_outside_test_mode(self) -> None:
        """Verify _safe_rollback() actually rollbacks outside test mode"""
        from odoo.tools import config

        # Need to patch both detection methods
        with patch.object(self.test_model.env.registry, "in_test_mode", return_value=False):
            with patch.object(config, "get", return_value=False):
                with patch.object(self.test_model.env.cr, "rollback") as mock_rollback:
                    # This should rollback because all test detections return False
                    self.test_model._safe_rollback()
                    mock_rollback.assert_called_once()

    def test_is_test_mode_detection_methods(self) -> None:
        """Check that test mode detection works correctly"""
        from odoo.tools import config

        # Check both detection methods
        registry_test_mode = self.test_model.env.registry.in_test_mode()
        config_test_enable = config.get("test_enable")
        is_test_mode = self.test_model._is_test_mode()

        # At least one method should detect test mode
        any_test_mode = registry_test_mode or config_test_enable
        self.assertTrue(
            any_test_mode,
            f"At least one test detection method should work. Registry: {registry_test_mode}, Config: {config_test_enable}",
        )

        # _is_test_mode should return True if either detection works
        self.assertTrue(is_test_mode, "_is_test_mode() should return True during tests")

    def test_new_cursor_context_in_test_mode(self) -> None:
        """Verify _new_cursor_context doesn't commit in test mode"""
        # Since we're in test mode, the method should create a new cursor
        # but not commit it when the context exits

        # Use the actual method without mocking to test real behavior
        with self.test_model._new_cursor_context() as new_env:
            # Verify we got a different environment with a different cursor
            self.assertIsNotNone(new_env)
            self.assertNotEqual(new_env.cr, self.test_model.env.cr)

            # Make a change in the new environment to test commit behavior
            new_env["res.partner"].create({"name": "Test Partner in New Cursor", "email": "test_new_cursor@example.com"})

        # After exiting, the partner should not exist in our main cursor
        # because commits don't happen in test mode
        partner = self.env["res.partner"].search([("email", "=", "test_new_cursor@example.com")])
        self.assertFalse(partner, "Partner should not exist in main cursor because no commit in test mode")

    def test_advisory_lock(self) -> None:
        """Test advisory lock acquisition and release"""
        with self.test_model._advisory_lock(12345) as acquired:
            self.assertTrue(acquired, "Should acquire advisory lock")

        # Verify lock was released
        self.env.cr.execute("SELECT pg_try_advisory_lock(%s)", [12345])
        self.assertTrue(self.env.cr.fetchone()[0], "Lock should be released")
        self.env.cr.execute("SELECT pg_advisory_unlock(%s)", [12345])
