from odoo import api, fields, models, _
from odoo.exceptions import UserError

class StockTransportApprovalRule(models.Model):
    _name = "stock.transport.approval.rule"
    _description = "STO Approval Rule"
    _order = "sequence, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    min_qty = fields.Float(string="Minimum total qty", default=0.0)
    max_qty = fields.Float(string="Maximum total qty", default=0.0,
                           help="0 means no upper limit")
    min_value = fields.Monetary(string="Minimum total value", default=0.0)
    max_value = fields.Monetary(string="Maximum total value", default=0.0,
                                help="0 means no upper limit")
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    approve_required = fields.Boolean(string="Requires approval", default=True,
                                      help="If checked, matching requests go to waiting_approval.")
    auto_create_picking = fields.Boolean(string="Auto-create Picking", default=False,
                                         help="If true and approval is not required, a picking will be created automatically on confirm.")
    approver_group_id = fields.Many2one('res.groups', string="Approver Group",
                                        help="Members of this group can approve requests that match this rule.")

    def matches(self, total_qty, total_value, company_id):
        """Return True if rule matches given totals and company."""
        if not self.active:
            return False
        if self.company_id and self.company_id.id != company_id:
            return False
        if total_qty < (self.min_qty or 0.0):
            return False
        if (self.max_qty or 0.0) and total_qty > self.max_qty:
            return False
        if total_value < (self.min_value or 0.0):
            return False
        if (self.max_value or 0.0) and self.max_value > 0 and total_value > self.max_value:
            return False
        return True


class StockTransportRequest(models.Model):
    _name = "stock.transport.request"
    _description = "Stock Transport Order Request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    name = fields.Char(string="Request Reference", required=True, copy=False,
                       default=lambda self: (self.env['ir.sequence'].next_by_code('stock.transport.request') or '/'))
    origin = fields.Char(string="Source Document")
    requesting_warehouse_id = fields.Many2one('stock.warehouse', string="From Warehouse", required=True)
    destination_warehouse_id = fields.Many2one('stock.warehouse', string="To Warehouse", required=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, required=True)
    requested_by = fields.Many2one('res.users', string="Requested By", default=lambda self: self.env.user)
    requested_date = fields.Datetime(string="Requested Date", default=fields.Datetime.now)
    line_ids = fields.One2many('stock.transport.request.line', 'request_id', string="Lines", copy=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('waiting_approval', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    total_qty = fields.Float(string="Total Quantity", compute='_compute_totals', store=True)
    total_value = fields.Monetary(string="Total Value", compute='_compute_totals', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    @api.depends('line_ids.product_uom_qty', 'line_ids.product_id')
    def _compute_totals(self):
        for rec in self:
            qty = sum(rec.line_ids.mapped('product_uom_qty'))
            value = 0.0
            for line in rec.line_ids:
                price = line.product_id.standard_price or 0.0
                # use product standard_price for valuation; change if you need list_price
                value += price * line.product_uom_qty
            rec.total_qty = qty
            rec.total_value = value

    def action_confirm(self):
        """Mark as confirmed and evaluate approval rules. If approval is required -> waiting_approval.
           Otherwise approve or create picking automatically according to matching rule."""
        rules = self.env['stock.transport.approval.rule'].search([('active', '=', True)], order='sequence asc')
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Please add at least one line before confirming."))
            matched_rule = None
            for rule in rules:
                if rule.matches(rec.total_qty, rec.total_value, rec.company_id.id):
                    matched_rule = rule
                    break
            if matched_rule:
                if matched_rule.approve_required:
                    rec.state = 'waiting_approval'
                    rec.message_post(body=_("Request requires approval (rule: %s).") % matched_rule.name)
                else:
                    # auto approve path
                    rec.state = 'approved'
                    rec.message_post(body=_("Request auto-approved by rule: %s") % matched_rule.name)
                    if matched_rule.auto_create_picking:
                        rec._create_internal_picking()
                        rec.state = 'done'
            else:
                # No rules matched: default behavior -> require approval
                rec.state = 'waiting_approval'
                rec.message_post(body=_("No approval rule matched. Request set to Waiting Approval."))

    def action_approve(self):
        """Approve request (must be called by appropriate user/group)."""
        for rec in self:
            if rec.state not in ('waiting_approval', 'confirmed'):
                raise UserError(_("Only requests in 'Waiting Approval' or 'Confirmed' can be approved."))
            rec.state = 'approved'
            rec.message_post(body=_("Request approved by %s") % self.env.user.display_name)
            rec._create_internal_picking()

    def check_availability(self):
        """Check if all products have enough stock in the source warehouse."""
        for rec in self:
            for line in rec.line_ids:
                qty_available = line.product_id.with_context(
                    warehouse=rec.requesting_warehouse_id.id
                ).qty_available
                if qty_available < line.product_uom_qty:
                    return False
                else:
                    line.linked_move_id.picking_id.action_assign()
        return True

    def action_done(self):
        """Create internal picking if enough stock is available."""
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_("Only approved requests can be marked as done."))
            if not rec.check_availability():
                raise UserError(_("Not enough stock in the source warehouse to fulfill this request."))
            rec.state = 'done'
            rec.message_post(body=_("Request completed and internal transfer created."))

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'
            rec.message_post(body=_("Request cancelled"))

    def action_set_draft(self):
        for rec in self:
            rec.state = 'draft'

    def _create_internal_picking(self):
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']

        for rec in self:
            # find internal picking type for the source warehouse
            picking_type = PickingType.search([('warehouse_id', '=', rec.requesting_warehouse_id.id), ('code', '=', 'internal')], limit=1)
            if not picking_type:
                picking_type = PickingType.search([('code', '=', 'internal')], limit=1)
            if not picking_type:
                raise UserError(_("No internal picking type defined. Configure an internal picking type in Inventory > Configuration."))

            picking_vals = {
                'picking_type_id': picking_type.id,
                'location_id': rec.requesting_warehouse_id.lot_stock_id.id,
                'location_dest_id': rec.destination_warehouse_id.lot_stock_id.id,
                'origin': rec.name,
                'company_id': rec.company_id.id,
            }
            picking = StockPicking.create(picking_vals)
            moves = []
            for line in rec.line_ids:
                uom = line.product_uom_id and line.product_uom_id.id or line.product_id.uom_id.id
                move_vals = {
                    'reference': line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.product_uom_qty,
                    'product_uom': uom,
                    'location_id': rec.requesting_warehouse_id.lot_stock_id.id,
                    'location_dest_id': rec.destination_warehouse_id.lot_stock_id.id,
                    'picking_id': picking.id,
                    'origin': rec.name,
                    'company_id': rec.company_id.id,
                }
                move = StockMove.create(move_vals)
                line.linked_move_id = move.id
                moves.append(move)
            # Confirm & assign
            try:
                picking.action_confirm()
            except Exception:
                # action_confirm might be named differently depending on Odoo version,
                # the call will raise if not available — we ignore to continue
                pass
            try:
                picking.action_assign()
            except Exception:
                pass
            rec.message_post(body=_("Internal picking %s created") % (picking.name))

class StockTransportRequestLine(models.Model):
    _name = "stock.transport.request.line"
    _description = "STO Request Line"

    request_id = fields.Many2one('stock.transport.request', string="Request", ondelete='cascade', required=True)
    product_id = fields.Many2one('product.product', string="Product", required=True)
    product_uom_id = fields.Many2one('uom.uom', string="UoM", required=True)
    product_uom_qty = fields.Float(string="Quantity", required=True, default=1.0)
    scheduled_date = fields.Datetime(string="Scheduled Date")
    note = fields.Text()
    linked_move_id = fields.Many2one('stock.move', string="Stock Move")

    @api.onchange('product_id')
    def _onchange_product_uom(self):
        for rec in self:
            if rec.product_id:
                rec.product_uom_id = rec.product_id.uom_id