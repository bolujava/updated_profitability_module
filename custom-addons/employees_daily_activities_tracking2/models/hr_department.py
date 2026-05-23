from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    is_technical = fields.Boolean(
        string='Technical Department',
        tracking=True
    )

    is_non_technical = fields.Boolean(string="Non-Technical Department", tracking=True)


    @api.constrains('is_technical', 'is_non_technical')
    def _check_department_type(self):
        for rec in self:
            if rec.is_technical and rec.is_non_technical:
                raise ValidationError(
                    "A department cannot be both Technical and Non-Technical."
                )
    
    team_lead_id = fields.Many2one(
        'hr.employee',
        string="Team Lead",
        store=True
    )