from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class CompanyTrainingReportWizard(models.TransientModel):
    _name = 'company.training.report.wizard'
    _description = 'Company Training Report Wizard'

    date_from = fields.Date(
        string='Date From',
        required=True,
        default=fields.Date.today().replace(day=1)  # First day of current month
    )

    date_to = fields.Date(
        string='Date To',
        required=True,
        default=fields.Date.today()
    )

    report_type = fields.Selection([
        ('summary', 'Summary Report'),
        ('detailed', 'Detailed Report'),
        ('department', 'Department-wise Report'),
        ('training', 'Training-wise Report'),
    ], string='Report Type', required=True, default='summary')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from > wizard.date_to:
                raise ValidationError(_('Date From cannot be later than Date To!'))

    def action_print_report(self):
        """Print the company training report"""
        data = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'report_type': self.report_type,
        }

        return self.env.ref('custom_training_management.action_report_company_training').report_action(
            self, data=data
        )