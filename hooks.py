import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """
    Post-initialization hook to rename the field destination_warehouse_id to providing_warehouse_id
    in the stock.transport.request model.
    """
    _logger.info("Running post_init_hook for omt_stock_transport_request")
    
    # Check if the old column exists
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='stock_transport_request' 
        AND column_name='destination_warehouse_id'
    """)
    
    if cr.fetchone():
        _logger.info("Found destination_warehouse_id column, renaming to providing_warehouse_id")
        
        # Check if the new column already exists
        cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='stock_transport_request' 
            AND column_name='providing_warehouse_id'
        """)
        
        if not cr.fetchone():
            # Rename the column
            cr.execute("""
                ALTER TABLE stock_transport_request 
                RENAME COLUMN destination_warehouse_id TO providing_warehouse_id
            """)
            _logger.info("Successfully renamed destination_warehouse_id to providing_warehouse_id")
        else:
            _logger.warning("Column providing_warehouse_id already exists, skipping rename")
    else:
        _logger.info("Column destination_warehouse_id does not exist, no migration needed")
    
    _logger.info("Completed post_init_hook for omt_stock_transport_request")
