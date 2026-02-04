from odoo import api, fields, models

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    transport_request_id = fields.Many2one('stock.transport.request', string="Transport Request")

    def write(self, vals):
        """Override write to check and confirm transport requests when pickings are done."""
        result = super(StockPicking, self).write(vals)
        if 'state' in vals:
            # Check if any transport requests need to be confirmed
            requests = self.mapped('transport_request_id').filtered(lambda r: r)
            for request in requests:
                request._check_and_confirm()
        return result
