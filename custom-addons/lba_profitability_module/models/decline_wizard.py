from odoo import models, fields, api
from odoo.exceptions import ValidationError




class DeclineRoleWizard(models.TransientModel):
    _name = 'decline.role.wizard'
    _description = 'Decline Role Wizard'

    project_id = fields.Many2one('project.project', string='Project', required=True)
    role_id = fields.Selection([
        ('project_manager', 'Project Manager'),
        ('team_lead', 'Team Lead'),
        ('department_manager', 'Department Manager')
    ], string="Role", required=True)
    reason = fields.Text(string="Reason for Declining", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res.update({
            'role_id': self.env.context.get('default_role'),
            'project_id': self.env.context.get('default_project_id'),
        })
        return res

    def action_decline_role(self):
        for wizard in self:
            project = wizard.project_id
            role = wizard.role_id
            reason = wizard.reason

            if not project or not role:
                raise ValidationError("Project and Role must be selected.")

            role_label = dict(self._fields['role_id'].selection).get(role)
            employee = getattr(project, role, False)
            old_value = employee.name if employee else ""

            # Log in project chatter
            project.message_post(
                body=f"<b>{role_label} role declined</b><br/>Reason: {reason}",
                message_type="comment",
                subtype_xmlid="mail.mt_comment"
            )

            # Send email notification
            project._send_role_decline_email(role, reason)

            # Create a change log entry
            self.env['project.change.log'].create({
                'name': f"{role_label} role declined",
                'project_id': project.id,
                'field_name': role,
                'old_value': old_value,
                'new_value': 'Declined',
                'user_id': self.env.user.id,
                'change_date': fields.Datetime.now(),
            })

            # Reset the role field and status
            values = {}
            if role == 'project_manager':
                values = {'project_manager': False, 'project_manager_status': False}
            elif role == 'team_lead':
                values = {'team_lead_id': False, 'team_lead_status': False}
            elif role == 'department_manager':
                values = {
                    'department_manager_id': False,
                    'department_manager_status': False,
                    'department_id': False  # Optional reset
                }

            project.write(values)

        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}

    def _send_role_decline_email(self, project, role, reason):
        pass
