"""Migration to fix autopost_bills NULL values in res.partner.

This migration addresses an Odoo 18 issue where partners created via SQL
(like the base company partner) don't have the autopost_bills field set,
causing NOT NULL constraint violations during tests.
"""

import logging

from odoo.sql_db import Cursor

_logger = logging.getLogger(__name__)


def migrate(cr: Cursor, version: str) -> None:
    """Set default autopost_bills value for partners missing it.

    The autopost_bills field from the account module has:
    - default='ask'
    - required=True

    However, partners created by base_data.sql before the account module
    loads don't have this field set, causing constraint violations.
    """
    _logger.info("Starting migration to fix autopost_bills NULL values...")

    # Count partners with NULL autopost_bills before fix
    cr.execute("SELECT COUNT(*) FROM res_partner WHERE autopost_bills IS NULL")
    null_count_before = cr.fetchone()[0]

    if null_count_before > 0:
        _logger.info(f"Found {null_count_before} partners with NULL autopost_bills")

        # Set default value for all partners with NULL autopost_bills
        cr.execute("""
            UPDATE res_partner 
            SET autopost_bills = 'ask' 
            WHERE autopost_bills IS NULL
        """)

        _logger.info(f"Updated {cr.rowcount} partner records")

    # Verify no partners have NULL autopost_bills after migration
    cr.execute("SELECT COUNT(*) FROM res_partner WHERE autopost_bills IS NULL")
    null_count_after = cr.fetchone()[0]

    if null_count_after == 0:
        _logger.info("✓ Migration successful: All partners have autopost_bills set")
    else:
        _logger.error(f"✗ Migration incomplete: {null_count_after} partners still have NULL autopost_bills")
