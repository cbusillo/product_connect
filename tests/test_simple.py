from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSimple(TransactionCase):
    def test_simple(self) -> None:
        self.assertEqual(1, 1)
        print("SIMPLE TEST EXECUTED")
