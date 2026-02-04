from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError

class StockTransportApprovalRule(models.Model):
    _name = "stock.transport.approval.rule"
    _description = "STO Approval Rule"
    _order = "sequence, id"
    _sql_constraints = [
        ('unique_company_warehouse', 'unique(company_id, providing_warehouse_id)', 
         'Only one rule per company and providing warehouse is allowed!')
    ]

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    providing_warehouse_id = fields.Many2one('stock.warehouse', string="Providing Warehouse", required=True)
    valid_qty = fields.Float(string="Valid Request Qty", default=0.0,
                             help="Maximum total quantity allowed for requests. 0 means no limit.")
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    approve_required = fields.Boolean(string="Requires approval", default=True,
                                      help="If checked, matching requests go to requested state.")
    auto_create_picking = fields.Boolean(string="Auto-create Picking", default=True,
                                         help="If true, pickings will be created automatically on approval.")
    approver_group_id = fields.Many2one('res.groups', string="Approver Group",
                                        help="Members of this group can approve requests that match this rule.")

    def matches(self, providing_warehouse_id, total_qty, company_id):
        """Return True if rule matches given warehouse, qty and company."""
        if not self.active:
            return False
        if self.company_id and self.company_id.id != company_id:
            return False
        if self.providing_warehouse_id.id != providing_warehouse_id:
            return False
        if self.valid_qty > 0.0 and total_qty > self.valid_qty:
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
    requesting_warehouse_id = fields.Many2one('stock.warehouse', string="Requesting Warehouse", required=True)
    providing_warehouse_id = fields.Many2one('stock.warehouse', string="Providing Warehouse", required=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, required=True)
    requested_by = fields.Many2one('res.users', string="Requested By", default=lambda self: self.env.user)
    requested_date = fields.Datetime(string="Requested Date", default=fields.Datetime.now)
    line_ids = fields.One2many('stock.transport.request.line', 'request_id', string="Lines", copy=True)
    picking_ids = fields.One2many('stock.picking', 'transport_request_id', string="Pickings")
    need_revision = fields.Boolean(string="Needs Revision", default=False,
                                   help="Set to True if the request exceeds allowed limits")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    total_qty = fields.Float(string="Total Quantity", compute='_compute_totals', store=True)
    total_value = fields.Monetary(string="Total Value", compute='_compute_totals', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    @api.depends('line_ids.product_uom_qty', 'line_ids.product_id')
    def _compute_totals(self):
        for rec in self:
            # Convert all quantities to product default UoM for summing
            qty = 0.0
            value = 0.0
            for line in rec.line_ids:
                # Convert requested qty from line UoM to product default UoM
                product_uom = line.product_id.uom_id
                if line.product_uom_id and product_uom:
                    qty_in_product_uom = line.product_uom_id._compute_quantity(
                        line.product_uom_qty, product_uom
                    )
                else:
                    qty_in_product_uom = line.product_uom_qty
                qty += qty_in_product_uom
                # use product standard_price for valuation
                price = line.product_id.standard_price or 0.0
                value += price * qty_in_product_uom
            rec.total_qty = qty
            rec.total_value = value

    def action_request(self):
        """Submit request for approval. Validates lines, computes totals, checks approval rules,
        validates per-line free qty and sets need_revision if checks fail."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft requests can be submitted."))
            if not rec.line_ids:
                raise UserError(_("Please add at least one line before submitting."))
            if not rec.requesting_warehouse_id or not rec.providing_warehouse_id:
                raise UserError(_("Both requesting and providing warehouses must be set."))
            
            # Reset need_revision
            rec.need_revision = False
            messages = []
            
            # Check per-line free qty in providing warehouse
            for line in rec.line_ids:
                # Convert requested qty to product default UoM for comparison
                product_uom = line.product_id.uom_id
                requested_qty = line.product_uom_qty
                if line.product_uom_id and product_uom:
                    requested_qty = line.product_uom_id._compute_quantity(
                        line.product_uom_qty, product_uom
                    )
                
                free_qty = line.product_id.with_context(
                    warehouse=rec.providing_warehouse_id.id
                ).qty_available
                
                if requested_qty > free_qty:
                    messages.append(
                        _("Product %s: requested %.2f %s but only %.2f available in %s") % (
                            line.product_id.display_name,
                            requested_qty,
                            product_uom.name,
                            free_qty,
                            rec.providing_warehouse_id.name
                        )
                    )
                    rec.need_revision = True
            
            # Check approval rules or warehouse fallback
            rules = self.env['stock.transport.approval.rule'].search(
                [('active', '=', True)], order='sequence asc'
            )
            matched_rule = None
            for rule in rules:
                if rule.matches(rec.providing_warehouse_id.id, rec.total_qty, rec.company_id.id):
                    matched_rule = rule
                    break
            
            # If no rule matched, check warehouse fallback valid_request_qty
            if not matched_rule:
                warehouse_limit = rec.providing_warehouse_id.valid_request_qty or 0.0
                if warehouse_limit > 0.0 and rec.total_qty > warehouse_limit:
                    messages.append(
                        _("Total quantity %.2f exceeds warehouse limit %.2f for %s") % (
                            rec.total_qty, warehouse_limit, rec.providing_warehouse_id.name
                        )
                    )
                    rec.need_revision = True
            
            # Set state to requested
            rec.state = 'requested'
            
            if rec.need_revision:
                rec.message_post(body=_("Request submitted but needs revision:<br/>%s") % "<br/>".join(messages))
            else:
                # Check if auto-approve applies
                if matched_rule and not matched_rule.approve_required:
                    rec.action_approve()
                else:
                    rec.message_post(body=_("Request submitted and waiting for approval."))

    def action_approve(self):
        """Approve request and create pickings. Only allowed when state is 'requested' and need_revision is False."""
        for rec in self:
            if rec.state != 'requested':
                raise UserError(_("Only requests in 'Requested' state can be approved."))
            if rec.need_revision:
                raise UserError(_("Cannot approve a request that needs revision. Please adjust quantities."))
            
            # Check if user has approver rights
            rules = self.env['stock.transport.approval.rule'].search(
                [('active', '=', True), ('providing_warehouse_id', '=', rec.providing_warehouse_id.id)], 
                order='sequence asc'
            )
            matched_rule = None
            for rule in rules:
                if rule.matches(rec.providing_warehouse_id.id, rec.total_qty, rec.company_id.id):
                    matched_rule = rule
                    break
            
            if matched_rule and matched_rule.approver_group_id:
                if matched_rule.approver_group_id.id not in self.env.user.groups_id.ids:
                    raise UserError(_("You are not authorized to approve this request."))
            
            rec.state = 'approved'
            rec.message_post(body=_("Request approved by %s") % self.env.user.display_name)
            rec._create_internal_picking()

    def action_set_draft(self):
        """Reset request to draft state."""
        for rec in self:
            rec.state = 'draft'
            rec.need_revision = False
            rec.message_post(body=_("Request reset to draft"))

    def action_cancel(self):
        """Cancel the request."""
        for rec in self:
            rec.state = 'cancelled'
            rec.message_post(body=_("Request cancelled"))

    def action_view_pickings(self):
        """Open the pickings related to this request."""
        self.ensure_one()
        action = self.env.ref('stock.action_picking_tree_all').read()[0]
        action['domain'] = [('id', 'in', self.picking_ids.ids)]
        action['context'] = {'create': False}
        return action

    def _check_and_confirm(self):
        """Called by picking write hook. If all pickings are done, set request to confirmed."""
        for rec in self:
            if rec.state == 'approved' and rec.picking_ids:
                all_done = all(picking.state == 'done' for picking in rec.picking_ids)
                if all_done:
                    rec.state = 'confirmed'
                    rec.message_post(body=_("All pickings completed. Request confirmed."))

    def _create_internal_picking(self):
        """Create internal picking(s) from providing warehouse to requesting warehouse."""
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']

        for rec in self:
            # Find internal picking type for the providing warehouse
            picking_type = PickingType.search([
                ('warehouse_id', '=', rec.providing_warehouse_id.id), 
                ('code', '=', 'internal')
            ], limit=1)
            if not picking_type:
                picking_type = PickingType.search([('code', '=', 'internal')], limit=1)
            if not picking_type:
                raise UserError(_("No internal picking type defined. Configure an internal picking type in Inventory > Configuration."))

            picking_vals = {
                'picking_type_id': picking_type.id,
                'location_id': rec.providing_warehouse_id.lot_stock_id.id,
                'location_dest_id': rec.requesting_warehouse_id.lot_stock_id.id,
                'origin': rec.name,
                'company_id': rec.company_id.id,
                'transport_request_id': rec.id,
            }
            picking = StockPicking.create(picking_vals)
            
            for line in rec.line_ids:
                uom = line.product_uom_id and line.product_uom_id.id or line.product_id.uom_id.id
                move_vals = {
                    'reference': line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.product_uom_qty,
                    'product_uom': uom,
                    'location_id': rec.providing_warehouse_id.lot_stock_id.id,
                    'location_dest_id': rec.requesting_warehouse_id.lot_stock_id.id,
                    'picking_id': picking.id,
                    'origin': rec.name,
                    'company_id': rec.company_id.id,
                }
                move = StockMove.create(move_vals)
                line.linked_move_id = move.id
            
            # Confirm and try to reserve
            try:
                picking.action_confirm()
                picking.action_assign()
            except Exception as e:
                rec.message_post(body=_("Picking created but could not be confirmed/assigned: %s") % str(e))
            
            rec.message_post(body=_("Internal picking %s created") % (picking.name))