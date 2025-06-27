from unittest.mock import patch, MagicMock

from odoo.tests import tagged

from ..tests.test_base import ProductConnectTransactionCase


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

        # Create a mock thread without testing attribute
        mock_thread = MagicMock()
        del mock_thread.testing  # Ensure no testing attribute

        # Need to patch all three detection methods
        with patch.object(self.test_model.env.registry, "in_test_mode", return_value=False):
            with patch("threading.current_thread", return_value=mock_thread):
                with patch.object(config, "get", return_value=False):
                    with patch.object(self.test_model.env.cr, "commit") as mock_commit:
                        # This should commit because all test detections return False
                        self.test_model._safe_commit()
                        mock_commit.assert_called_once()

    def test_safe_rollback_outside_test_mode(self) -> None:
        """Verify _safe_rollback() actually rollbacks outside test mode"""
        from odoo.tools import config

        # Create a mock thread without testing attribute
        mock_thread = MagicMock()
        del mock_thread.testing  # Ensure no testing attribute

        # Need to patch all three detection methods
        with patch.object(self.test_model.env.registry, "in_test_mode", return_value=False):
            with patch("threading.current_thread", return_value=mock_thread):
                with patch.object(config, "get", return_value=False):
                    with patch.object(self.test_model.env.cr, "rollback") as mock_rollback:
                        # This should rollback because all test detections return False
                        self.test_model._safe_rollback()
                        mock_rollback.assert_called_once()

    def test_threading_detection_fallback(self) -> None:
        """Test if threading detection is actually needed"""
        # Create a mock thread with testing attribute
        mock_thread = MagicMock()
        mock_thread.testing = True

        with patch.object(self.test_model.env.registry, "in_test_mode", return_value=False):
            with patch("threading.current_thread", return_value=mock_thread):
                with patch.object(self.test_model.env.cr, "commit") as mock_commit:
                    # This should NOT commit because thread has testing=True
                    self.test_model._safe_commit()
                    mock_commit.assert_not_called()

    def test_threading_detection_no_attribute(self) -> None:
        """Test behavior when thread has no testing attribute"""
        from odoo.tools import config

        # Create a mock thread without testing attribute
        mock_thread = MagicMock()
        del mock_thread.testing  # Remove the attribute

        # Patch all detection methods
        with patch.object(self.test_model.env.registry, "in_test_mode", return_value=False):
            with patch("threading.current_thread", return_value=mock_thread):
                with patch.object(config, "get", return_value=False):
                    with patch.object(self.test_model.env.cr, "commit") as mock_commit:
                        # This SHOULD commit because all test detections return False
                        self.test_model._safe_commit()
                        mock_commit.assert_called_once()

    def test_check_current_thread_attributes(self) -> None:
        """Check what test detection methods work during tests"""
        import threading
        from odoo.tools import config

        current_thread = threading.current_thread()

        # Check all three detection methods
        registry_test_mode = self.test_model.env.registry.in_test_mode()
        config_test_enable = config.get("test_enable")
        thread_testing = getattr(current_thread, "testing", False)

        # Log findings
        print(f"Registry in_test_mode(): {registry_test_mode}")
        print(f"Config test_enable: {config_test_enable}")
        print(f"Thread testing attribute: {thread_testing}")

        # At least one method should detect test mode
        any_test_mode = registry_test_mode or config_test_enable or thread_testing
        self.assertTrue(
            any_test_mode,
            f"At least one test detection method should work. "
            f"Registry: {registry_test_mode}, Config: {config_test_enable}, Thread: {thread_testing}",
        )
