from odoo import api, fields, _, models

class PurchaseLimitConfig(models.Model):
    _name = 'purchase.limit.config'
    _description = 'Configuración de Límites de Compra'

    name_config = fields.Char(string="Configuración", default="Configuración del Límite de Compras", readonly=True, tracking=True)
    quantity_limit = fields.Float(string="Cantidad limite de compra", tracking=True)
    current_limit = fields.Float(string='Límite Actual de compra', compute='_compute_current_limit', readonly=True, store=True, tracking=True)
    note = fields.Text(string="Nota", store=True, tracking=True)

    create_date = fields.Datetime(string='Fecha de Creación', readonly=True, tracking=True)
    write_date = fields.Datetime(string='Última Modificación', readonly=True, tracking=True)
    write_uid = fields.Many2one('res.users', string='Modificado Por', readonly=True, tracking=True)



    @api.depends('quantity_limit')
    def _compute_current_limit(self):
        for record in self:
            record.current_limit = record.quantity_limit

    def name_get(self):
        result = []
        for record in self:
            name = "Configuración del Límite de Compras"
            result.append((record.id, name))
        return result