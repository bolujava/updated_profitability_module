from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
import logging

_logger = logging.getLogger(__name__)


class AssignTrainingWizard(models.TransientModel):
    _name = 'assign.training.wizard'
    _description = 'Assign Training Wizard'

    course_id = fields.Many2one('training.course', string='Training', required=True)

    # Assignment options
    assignment_type = fields.Selection([
        ('individual', 'Individual Employees'),
        ('department', 'Entire Department(s)'),
        ('company', 'Entire Company')
    ], string='Assign To', required=True, default='individual')

    # For individual assignment
    employee_ids = fields.Many2many('hr.employee', string='Employees')

    # For department assignment
    department_ids = fields.Many2many('hr.department', string='Departments')

    # Common fields
    date_start = fields.Date(string='Start Date', required=True, default=fields.Date.today)
    date_end = fields.Date(string='Due Date', required=True)
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Priority', default='1')

    @api.onchange('assignment_type')
    def _onchange_assignment_type(self):
        """Clear selections when changing assignment type"""
        self.employee_ids = False
        self.department_ids = False

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_end < record.date_start:
                raise ValidationError('Due Date cannot be earlier than Start Date.')

    def action_assign(self):
        """Main method to assign training based on selection"""
        self.ensure_one()

        # Check permissions
        if self.assignment_type == 'company' and not self.env.user.has_group(
                'custom_training_management.group_training_admin'):
            raise AccessError(_('Only People Services can assign company-wide training.'))

        attendees = self.env['training.attendee']

        if self.assignment_type == 'individual':
            attendees = self._assign_individual()
        elif self.assignment_type == 'department':
            attendees = self._assign_department()
        elif self.assignment_type == 'company':
            attendees = self._assign_company()

        # Send notifications
        self._send_assignment_notifications(attendees)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Assigned Trainings',
            'res_model': 'training.attendee',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', attendees.ids)],
        }

    def _assign_individual(self):
        """Assign to selected individual employees"""
        if not self.employee_ids:
            raise ValidationError(_('Please select at least one employee.'))

        attendees = self.env['training.attendee']
        for employee in self.employee_ids:
            # Check if already assigned
            existing = self.env['training.attendee'].search([
                ('course_id', '=', self.course_id.id),
                ('employee_id', '=', employee.id)
            ])
            if existing:
                continue

            attendee = self.env['training.attendee'].create({
                'course_id': self.course_id.id,
                'employee_id': employee.id,
                'assigned_by': self.env.user.id,
                'date_start': self.date_start,
                'date_end': self.date_end,
                'priority': self.priority,
                'assignment_type': 'individual',
            })
            attendees |= attendee

        return attendees

    def _assign_department(self):
        """Assign to all employees in selected departments"""
        if not self.department_ids:
            raise ValidationError(_('Please select at least one department.'))

        attendees = self.env['training.attendee']
        employees = self.env['hr.employee'].search([('department_id', 'in', self.department_ids.ids)])

        for employee in employees:
            # Check if already assigned
            existing = self.env['training.attendee'].search([
                ('course_id', '=', self.course_id.id),
                ('employee_id', '=', employee.id)
            ])
            if existing:
                continue

            attendee = self.env['training.attendee'].create({
                'course_id': self.course_id.id,
                'employee_id': employee.id,
                'assigned_by': self.env.user.id,
                'date_start': self.date_start,
                'date_end': self.date_end,
                'priority': self.priority,
                'assignment_type': 'department',
            })
            attendees |= attendee

        return attendees

    def _assign_company(self):
        """Assign to all employees in the company"""
        attendees = self.env['training.attendee']
        employees = self.env['hr.employee'].search([])

        for employee in employees:
            # Check if already assigned
            existing = self.env['training.attendee'].search([
                ('course_id', '=', self.course_id.id),
                ('employee_id', '=', employee.id)
            ])
            if existing:
                continue

            attendee = self.env['training.attendee'].create({
                'course_id': self.course_id.id,
                'employee_id': employee.id,
                'assigned_by': self.env.user.id,
                'date_start': self.date_start,
                'date_end': self.date_end,
                'priority': self.priority,
                'assignment_type': 'company',
            })
            attendees |= attendee

        return attendees

    def _send_assignment_notifications(self, attendees):
        template = self.env.ref(
            'custom_training_management.email_template_training_assignment',
            raise_if_not_found=False
        )

        if not template:
            _logger.warning("Training Assignment template not found")
            return

        for attendee in attendees:
            if not attendee.employee_id.work_email:
                continue

            try:
                # Flush & commit to ensure record exists
                attendee.flush()
                self.env.cr.commit()

                fresh_record = attendee.sudo().browse(attendee.id)

                template.sudo().send_mail(
                    fresh_record.id,
                    force_send=True,
                    raise_exception=True,
                    email_values={
                        'email_to': fresh_record.employee_id.work_email,
                        'email_from': fresh_record.company_id.email or self.env.user.email,
                    }
                )

            except Exception as e:
                _logger.exception("Failed to send training email: %s", e)
