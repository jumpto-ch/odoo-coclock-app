import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    _logger.info("=== PRE-MIGRATION STARTED for module rename odoo-coclock-app → odoo_coclock_app ===")

    # Check if the old module exists
    cr.execute("""
        SELECT name, state 
        FROM ir_module_module 
        WHERE name = 'odoo-coclock-app';
    """)
    old = cr.fetchall()
    _logger.info("Old module entries found: %s", old)

    # Rename the module in ir_module_module
    cr.execute("""
        UPDATE ir_module_module
        SET name = 'odoo_coclock_app'
        WHERE name = 'odoo-coclock-app';
    """)
    _logger.info("Renamed module 'odoo_coclock_app' in ir_module_module")

    # Rename in dependencies
    cr.execute("""
        UPDATE ir_module_module_dependency
        SET name = 'odoo_coclock_app'
        WHERE name = 'odoo-coclock-app';
    """)
    _logger.info("Renamed module 'odoo_coclock_app' in ir_module_module_dependency")

    # Re-check after update
    cr.execute("""
        SELECT name, state 
        FROM ir_module_module 
        WHERE name = 'odoo_coclock_app';
    """)
    new_entries = cr.fetchall()
    _logger.info("New module entries after rename: %s", new_entries)

    _logger.info("=== PRE-MIGRATION COMPLETED ===")
