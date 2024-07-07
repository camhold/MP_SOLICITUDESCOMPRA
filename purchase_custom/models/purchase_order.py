from odoo import api, fields, _, models, exceptions
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    employee_id = fields.Many2one('hr.employee', compute='_compute_employee_id', compute_sudo=True)
    employee_departament_id = fields.Many2one(related="employee_id.department_id")
    department_id = fields.Many2one('hr.department', domain='[("id", "=", employee_departament_id)]')
    is_acquisition = fields.Boolean(related='employee_id.department_id.is_acquisition')
    see_supplier = fields.Boolean(related='employee_id.department_id.see_supplier')
    is_foreign = fields.Boolean(default=False)
    partner_id = fields.Many2one(required=False)
    request_user_id = fields.Many2one('res.partner')
    product_type = fields.Selection(related="order_line.product_id.product_tmpl_id.type", string="Tipo de Producto", readonly=True)
    show_partner_id = fields.Boolean(string="Show Partner ID", compute='_compute_show_partner_id')

    limit_config_id = fields.Many2one('purchase.limit.config', string='Configuración de Límite', default=lambda self: self.env['purchase.limit.config'].search([],order='id desc', limit=1).id)
    current_limit = fields.Float(string='Límite Actual', related='limit_config_id.current_limit', store=True, readonly=True)
    state = fields.Selection([
        ('draft', 'RFQ'),
        ('limit_approval', 'Autorización por Límite'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='Status', track_visibility='onchange', copy=False, index=True, readonly=True, default='draft', required=True)

    @api.model
    def default_get(self, fields_list):
        defaults = super(PurchaseOrder, self).default_get(fields_list)
        defaults['employee_id'] = self.env['hr.employee'].search([('user_id', '=', self.env.context.get('uid'))])
        return defaults

    def _compute_employee_id(self):
        for purchase_order_id in self:
            employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.context.get('uid'))], limit=1)
            if not employee_id:
                raise UserError(_('There is no employee related to this user.'))
            else:
                purchase_order_id.employee_id = employee_id

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if not val['user_id']:
                val['partner_id'] = self.env.user.partner_id.id
                val['request_user_id'] = self.env.user.partner_id.id
            employee_id = self.env['hr.employee'].search([('user_id', '=', val['user_id'])])
            if not employee_id:
                raise UserError(_('There is no employee related to this user.'))
            if not val['partner_id']:
                val['partner_id'] = self.env.user.partner_id.id
            if len(employee_id) == 1 and val['user_id']:
                val['employee_id'] = employee_id.id
            val['request_user_id'] = self.env.user.partner_id.id
        res = super().create(vals_list)
        return res

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        if self.partner_id == self.request_user_id:
            raise UserError(_('The provider cannot be the same as the requesting user, please correct.'))
        return res


    def _get_order_state(self):
        for order in self:
            max_amount_limit = order.current_limit
            if max_amount_limit:
                order_amount = sum(line.price_unit * line.product_qty for line in order.order_line)
                if order_amount > max_amount_limit:
                    odoobot = self.env.ref('base.partner_root')
                    if odoobot:
                        order.message_post(
                            body='El monto del pedido ha excedido el límite permitido y pasará a un estado de "Autorización por límite".',
                            message_type='notification',
                            partner_ids=[odoobot.id]
                        )
                    return 'limit_approval'
        return 'draft'

    @api.model
    def create(self, vals):
        order = super(PurchaseOrder, self).create(vals)
        order.write({'state': order._get_order_state()})
        return order

    def write(self, vals):
        res = super(PurchaseOrder, self).write(vals)
        if 'order_line' in vals or 'current_limit' in vals:
            for order in self:
                order.write({'state': order._get_order_state()})
        return res

    def write(self, vals):
        res = super(PurchaseOrder, self).write(vals)
        for order in self:
            if 'state' in vals and vals['state'] == 'limit_approval':
                employee = order.env.user.employee_id
                if employee and employee.parent_id:
                    order.env['mail.activity'].create({
                        'res_id': order.id,
                        'res_model_id': order.env.ref('purchase.model_purchase_order').id,
                        'summary': 'Revisar orden con límite de compra excedido',
                        'note': 'La orden de compra %s ha excedido el límite de compra.' % (order.name),
                        'user_id': employee.parent_id.user_id.id,
                    })
        return res

    def _check_manager_permission(self):
        for order in self:
            created_by_user = order.create_uid
            created_by_employee = created_by_user.employee_id
            if created_by_employee and created_by_employee.parent_id:
                if order.env.user == created_by_employee.parent_id.user_id:
                    return True
        return False

    def action_approve_limit(self):
        for order in self:
            if not order._check_manager_permission():
                raise UserError(_("Solo el gerente del departamento del empleado puede aprobar la orden."))
            order.write({'state': 'draft'})

    @api.depends('product_id')
    def _compute_show_partner_id(self):
        for record in self:
            if self.env.user.has_group('purchase.group_purchase_manager'):
                record.show_partner_id = True
            elif record.product_id:
                record.show_partner_id = (
                    record.product_id.product_tmpl_id.detailed_type == 'service' and
                    record.product_id.type == 'service'
                )
            else:
                record.show_partner_id = False

    @api.constrains('order_line')
    def _check_product_types(self):
        for order in self:
            if not order.is_foreign:
                for line in order.order_line:
                    if line.product_type == 'service':
                        other_product_types = order.order_line.filtered(lambda x: x != line and x.product_type)
                        if any(line.product_type != 'service' for line in other_product_types):
                            raise ValidationError('Los productos de tipo "service" no pueden combinarse con otros tipos de productos.')
                    elif line.product_type == 'product':
                        other_product_types = order.order_line.filtered(lambda x: x != line and x.product_type)
                        if any(x.product_type == 'consu' for x in other_product_types):
                            raise ValidationError('Los productos de tipo "product" no pueden combinarse con productos de tipo "consu".')