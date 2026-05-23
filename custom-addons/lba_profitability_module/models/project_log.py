from odoo import models, fields, api

class ProjectChangeLog(models.Model):
    _name = 'project.change.log'
    _description = 'Project Change Log'
    _order = 'change_date desc'

    name = fields.Char(string="Description")
    project_id = fields.Many2one('project.project', string='Project', required=True)
    field_name = fields.Char(string='Field Name', required=True)
    old_value = fields.Char(string='Old Value')
    new_value = fields.Char(string='New Value')
    user_id = fields.Many2one('res.users', string='Changed By', default=lambda self: self.env.user)
    change_date = fields.Datetime(string='Date Changed', default=fields.Datetime.now)

    def __str__(self):
        return f"ChangeLog: {self.name or 'Unnamed'} for {self.project_id.name or 'Unknown Project'} on {self.change_date.strftime('%Y-%m-%d %H:%M:%S') if self.change_date else 'Unknown Date'}"
