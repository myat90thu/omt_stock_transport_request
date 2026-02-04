from odoo import fields, models

class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    valid_request_qty = fields.Float(
        string="Valid Request Qty",
        default=0.0,
        help="Maximum total quantity allowed for transport requests from this warehouse. 0 means no limit."
    )
