from odoo import fields, models, api
from odoo.exceptions import ValidationError

class StockTransportApprovalRuleLine(models.Model):
    _name = "stock.transport.approval.rule.line"
    _description = "STO Approval Rule Line"
    _sql_constraints = [
        ('unique_rule_product', 'unique(approval_rule_id, product_id)', 
         'Product must be unique per approval rule!')
    ]

    approval_rule_id = fields.Many2one('stock.transport.approval.rule', string="Approval Rule", required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", required=True)
    valid_request_qty = fields.Float(
        string="Valid Request Qty",
        default=0.0,
        help="Maximum quantity allowed for this product in transport requests. 0 means no limit."
    )

    @api.constrains('valid_request_qty')
    def _check_valid_request_qty(self):
        for rec in self:
            if rec.valid_request_qty < 0:
                raise ValidationError("Valid Request Qty cannot be negative.")
