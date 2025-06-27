from contextlib import contextmanager
from typing import Generator

from odoo import api, models
from odoo.tools import config


class TransactionMixin(models.AbstractModel):
    _name = "transaction.mixin"
    _description = "Helper methods for transaction management"

    def _safe_commit(self) -> None:
        if not self._is_test_mode():
            self.env.cr.commit()

    def _safe_rollback(self) -> None:
        if not self._is_test_mode():
            self.env.cr.rollback()

    def _is_test_mode(self) -> bool:
        return self.env.registry.in_test_mode() or config.get("test_enable")

    @contextmanager
    def _new_cursor_context(self, commit: bool = True) -> Generator[api.Environment, None, None]:
        new_cr = self.env.registry.cursor()
        try:
            new_env = api.Environment(new_cr, self.env.uid, self.env.context, su=True)
            yield new_env
            if commit and not self._is_test_mode():
                new_cr.commit()
        finally:
            new_cr.close()

    @contextmanager
    def _advisory_lock(self, lock_id: int) -> Generator[bool, None, None]:
        cr = self.env.cr
        cr.execute("SELECT pg_try_advisory_lock(%s)", [lock_id])
        if not cr.fetchone()[0]:
            yield False
            return
        try:
            yield True
        finally:
            cr.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
