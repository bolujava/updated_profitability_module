from email.policy import default

# models/project_job_rate.py
from odoo import models, fields, api

class ProjectJobRate(models.Model):
    _name = 'project.job.rate'
    _description = 'Project Job Rate'
    _rec_name = 'name'

    name = fields.Char(string="Resource", required=True)
    hourly_rate = fields.Float(string="Hourly Rate (₦/hr)", required=True)
    daily_rate = fields.Float(
        string="Daily Rate (₦/day)",
        compute="_compute_daily_rate",
        inverse="_inverse_daily_rate",
        store=True,
    )
    cost_rate = fields.Float(string="Internal Cost Rate (₦/hr)", default=0.0, required=True)
    selling_rate = fields.Float(string="Selling Rate (₦/hr)", default=0.0, required=True)  # you may keep or remove

    product_id = fields.Many2one('product.product', string="Linked Product")
    active = fields.Boolean(string="Active", default=True)

    @api.depends('hourly_rate')
    def _compute_daily_rate(self):
        for rec in self:
            rec.daily_rate = rec.hourly_rate * 8 if rec.hourly_rate else 0.0

    def _inverse_daily_rate(self):
        for rec in self:
            rec.hourly_rate = rec.daily_rate / 8 if rec.daily_rate else 0.0

    @api.model
    def create(self, vals):
        if vals.get('hourly_rate') and not vals.get('daily_rate'):
            vals['daily_rate'] = vals['hourly_rate'] * 8
        elif vals.get('daily_rate') and not vals.get('hourly_rate'):
            vals['hourly_rate'] = vals['daily_rate'] / 8

        rec = super().create(vals)

        product_vals = {
            'name': rec.name,
            'type': 'service',
            'sale_ok': True,
            'purchase_ok': True,
            # **Use hourly_rate as the product sale price**
            'lst_price': rec.hourly_rate,
            # Use cost_rate as product cost
            'standard_price': rec.hourly_rate,
        }
        if not rec.product_id:
            rec.product_id = self.env['product.product'].create(product_vals)
        else:
            rec.product_id.write(product_vals)
        return rec

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.product_id and not self.env.context.get('sync_from_product'):
                # ensure product price = hourly_rate, product cost = cost_rate
                rec.product_id.with_context(sync_from_job_rate=True).write({
                    'name': rec.name,
                    'lst_price': rec.hourly_rate,
                    'standard_price': rec.hourly_rate,
                })
        return res

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                # when linking an existing product -> adopt its prices into the job rate
                rec.hourly_rate = rec.product_id.lst_price or 0.0
                rec.cost_rate = rec.product_id.standard_price or 0.0
                rec.selling_rate = rec.product_id.lst_price or 0.0
