from odoo import api, fields, models, _

class StockTransportRequestLine(models.Model):
    _name = "stock.transport.request.line"
    _description = "Stock Transport Order Request Line"

    request_id = fields.Many2one('stock.transport.request', string="Request", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", required=True)
    product_uom_id = fields.Many2one('uom.uom', string="UoM", required=True)
    product_uom_qty = fields.Float(string="Quantity", required=True, default=1.0)
    scheduled_date = fields.Datetime(string="Scheduled Date")
    note = fields.Text(string="Notes")
    linked_move_id = fields.Many2one('stock.move', string="Stock Move")