from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Request Reference', required=True, copy=False, readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code('purchase.request') or _('New'))
    description = fields.Text(string='Description')
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today, required=True)
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rfq', 'RFQ Generated'),
        ('order', 'Order Confirmed')
    ], string='Status', default='draft', track_visibility='onchange')

    product_ids = fields.One2many('purchase.request.line', 'request_id', string='Products')

    def action_request(self):
        if not self.product_ids:
            raise UserError(_('You cannot request a purchase without any products.'))
        self.state = 'requested'

    def action_approve(self):
        if not self.env.user.has_group('purchase_request.group_purchase_manager'):
            raise UserError(_('Only a manager can approve a purchase request.'))
        self.state = 'approved'
        self.approved_by = self.env.user

    def action_generate_rfq(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Only approved requests can generate an RFQ.'))
        purchase_order = self.env['purchase.order'].create({
            'partner_id': self.env['res.partner'].search([], limit=1).id,  # Example vendor, adjust as needed
            'order_line': [(0, 0, {
                'product_id': line.product_id.id,
                'product_qty': line.quantity,
                'price_unit': line.product_id.standard_price,
                'date_planned': fields.Date.today(),
            }) for line in self.product_ids]
        })
        self.state = 'rfq'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Request for Quotation'),
            'view_mode': 'form',
            'res_model': 'purchase.order',
            'res_id': purchase_order.id,
        }

    def action_confirm_order(self):
        if self.state != 'rfq':
            raise UserError(_('You need to generate an RFQ before confirming an order.'))
        self.state = 'order'


class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Request Line'

    request_id = fields.Many2one('purchase.request', string='Purchase Request', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
