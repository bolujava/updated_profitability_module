from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    employee_type = fields.Selection(
        [('technical', 'Technical'), ('non_technical', 'Non-Technical'), ('employee','Employee')],
        string="Employee Type",
        compute="_compute_employee_type",
        store=True,
    )


    team_lead_id = fields.Many2one(
        'hr.employee',
        string="Team Lead",
        compute='_compute_team_lead',
        store=True,
        readonly=False
    )

    @api.depends('department_id', 'department_id.team_lead_id')  #
    def _compute_team_lead(self):
        for emp in self:
            emp.team_lead_id = emp.department_id.team_lead_id



    @api.depends('department_id')
    def _compute_employee_type(self):
        for emp in self:
            if emp.department_id.is_technical:
                emp.employee_type = 'technical'
            elif emp.department_id.is_non_technical:
                emp.employee_type = 'non_technical'
            else:
                emp.employee_type = 'employee'  # fallback for invalid/missing data


    @api.model
    def create(self, vals):
        if 'employee_type' in vals and vals['employee_type'] not in ['technical', 'non_technical', 'employee', False]:
            vals['employee_type'] = False
        return super().create(vals)

    def write(self, vals):
        if 'employee_type' in vals and vals['employee_type'] not in ['technical', 'non_technical', 'employee', False]:
            vals['employee_type'] = False
        return super().write(vals)
