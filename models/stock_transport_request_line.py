from odoo import api, fields, models, _

class StockTransportRequestLine(models.Model):
    _name = "stock.transport.request.line"
    _description = "Stock Transport Order Request Line"

    request_id = fields.Many2one('stock.transport.request', string="Request", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", required=True)
    product_uom_id = fields.Many2one('uom.uom', string="UoM", required=True)
    product_uom_qty = fields.Float(string="Quantity", required=True, default=1.0)
    product_free_qty = fields.Float(string="Free Qty", readonly=True,
                                     help="Available quantity in the providing warehouse")
    note = fields.Text(string="Notes")
    linked_move_id = fields.Many2one('stock.move', string="Stock Move")

    @api.onchange('product_id', 'request_id.providing_warehouse_id')
    def _onchange_product_free_qty(self):
        """onchange the available quantity of the product in the providing warehouse."""
        for rec in self:
            if rec.product_id and rec.request_id and rec.request_id.providing_warehouse_id:
                rec.product_free_qty = rec.product_id.with_context(
                    warehouse=rec.request_id.providing_warehouse_id.id
                ).free_qty
            else:
                rec.product_free_qty = 0.0

    @api.onchange('product_id')
    def _onchange_product_uom(self):
        """Set product UoM when product is selected."""
        for rec in self:
            if rec.product_id:
                rec.product_uom_id = rec.product_id.uom_id