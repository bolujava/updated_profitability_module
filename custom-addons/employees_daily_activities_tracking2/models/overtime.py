from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class EmployeeOvertime(models.Model):
    _name = 'employee.overtime'
    _description = 'Employee Overtime Entry'
    _order = 'start_datetime desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        required=True,
        default=lambda self: self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1
        )
    )

    start_datetime = fields.Datetime(
        string="Start Time",
        required=True,
        tracking=True
    )

    end_datetime = fields.Datetime(
        string="End Time",
        required=True,
        tracking=True
    )

    daily_overtime_hours = fields.Float(
        string="Daily Overtime (Hours)",
        compute="_compute_daily_overtime",
        store=True
    )

    department_ids = fields.Many2many(
        'hr.department',
        string='Allowed Departments',
        required=True
    )
    weekly_overtime_hours = fields.Float(
        string="Weekly Overtime (Hours)",
        compute="_compute_weekly_overtime",
        store=True
    )

    weekly_start = fields.Date(
        string="Week Start",
        compute='_compute_week_range',
        store=True
    )
    weekly_end = fields.Date(
        string="Week End",
        compute='_compute_week_range',
        store=True
    )

    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed')],
        default='draft'
    )

    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        store=True,
        readonly=True
    )

    description = fields.Text(string="OverTime Justification", required=True, store=True)

    custom_activity_type_id = fields.Many2one(
        'activity.type',
        string="Task Type:",
        domain="[('department_ids', 'in', department_id)]",
        required=True,
        tracking=True
    )

    activity_name = fields.Char(
        string="Task Name:",
        related='custom_activity_type_id.name',
        readonly=True
    )

    activity_res_model = fields.Char(
        related='custom_activity_type_id.res_model',
        store=False,
        readonly=True
    )

    # Links
    helpdesk_ticket_id = fields.Many2one('helpdesk.ticket', string="Support Task:")

    project_id = fields.Many2one('project.project', string="Project Task:")
    crm_opportunity_id = fields.Many2one('crm.lead', string="Pre-Sales Task:")
    training_attendee_id = fields.Many2one(
        'training.course',
        string="Training Activity"
    )
    training_code = fields.Char(
        string="Training Code",
        related='training_attendee_id.training_code',
        store=True,
        readonly=True
    )

    @api.constrains('custom_activity_type_id', 'helpdesk_ticket_id', 'project_id', 'crm_opportunity_id',
                    'training_attendee_id')
    def _check_overtime_required_fields(self):
        for rec in self:
            model = rec.custom_activity_type_id.res_model if rec.custom_activity_type_id else False
            if model == 'helpdesk.ticket' and not rec.helpdesk_ticket_id:
                raise ValidationError("Support Task must be set for this task type.")
            elif model == 'project.project' and not rec.project_id:
                raise ValidationError("Project Task must be set for this task type.")
            elif model == 'crm.lead' and not rec.crm_opportunity_id:
                raise ValidationError("Pre-Sales Task must be set for this task type.")
            elif model == 'training.course' and not rec.training_attendee_id:
                raise ValidationError("Training Activity must be set for this task type.")

    name = fields.Char(
        string="Task Summary",
        compute="_compute_name",
        store=True,
        tracking=True
    )

    res_model = fields.Char(
        string="Related Model",
        default='employee.overtime',
        readonly=True
    )

    @api.depends('employee_id')
    def _compute_name(self):
        for rec in self:
            emp = rec.employee_id.name or 'Employee'
            rec.name = f"{emp}"

    @api.onchange('custom_activity_type_id')
    def _onchange_activity_type(self):
        for rec in self:
            rec.helpdesk_ticket_id = False
            rec.project_id = False
            rec.crm_opportunity_id = False
            rec.training_attendee_id = False

            if not rec.custom_activity_type_id:
                return {
                    'domain': {
                        'helpdesk_ticket_id': [('id', '=', 0)],
                        'project_id': [('id', '=', 0)],
                        'crm_opportunity_id': [('id', '=', 0)],
                        'training_attendee_id': [('id', '=', 0)],
                    }
                }

            model = rec.custom_activity_type_id.res_model
            if model == 'helpdesk.ticket':
                return {'domain': {
                    'helpdesk_ticket_id': [('id', '!=', False)],
                    'project_id': [('id', '=', 0)],
                    'crm_opportunity_id': [('id', '=', 0)],
                    'training_attendee_id': [('id', '=', 0)],
                }}
            elif model == 'project.project':
                return {'domain': {
                    'project_id': [('id', '!=', False)],
                    'helpdesk_ticket_id': [('id', '=', 0)],
                    'crm_opportunity_id': [('id', '=', 0)],
                    'training_attendee_id': [('id', '=', 0)],
                }}
            elif model == 'crm.lead':
                return {'domain': {
                    'crm_opportunity_id': [('type', '=', 'opportunity')],
                    'helpdesk_ticket_id': [('id', '=', 0)],
                    'project_id': [('id', '=', 0)],
                    'training_attendee_id': [('id', '=', 0)],
                }}
            elif model == 'training.course':
                return {'domain': {
                    'training_attendee_id': [('id', '!=', False)],
                    'helpdesk_ticket_id': [('id', '=', 0)],
                    'project_id': [('id', '=', 0)],
                    'crm_opportunity_id': [('id', '=', 0)],
                }}

    date = fields.Date(string="Date", compute="_compute_date", store=True)

    @api.depends('start_datetime')
    def _compute_date(self):
        for rec in self:
            rec.date = rec.start_datetime.date() if rec.start_datetime else False

    # -------------------------------
    # Compute daily overtime
    # -------------------------------
    @api.depends('start_datetime', 'end_datetime')
    def _compute_daily_overtime(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime:
                if rec.end_datetime < rec.start_datetime:
                    raise ValidationError("End time cannot be before start time.")
                delta = rec.end_datetime - rec.start_datetime
                rec.daily_overtime_hours = round(delta.total_seconds() / 3600, 2)
            else:
                rec.daily_overtime_hours = 0.0

    # -------------------------------
    # Compute week start and end
    # -------------------------------
    @api.depends('start_datetime')
    def _compute_week_range(self):
        for rec in self:
            if rec.start_datetime:
                iso_year, iso_week, iso_weekday = rec.start_datetime.date().isocalendar()
                rec.weekly_start = rec.start_datetime.date() - timedelta(days=iso_weekday - 1)
                rec.weekly_end = rec.weekly_start + timedelta(days=6)

    # -------------------------------
    # Compute weekly overtime
    # -------------------------------
    @api.depends('employee_id', 'start_datetime', 'daily_overtime_hours')
    def _compute_weekly_overtime(self):
        for rec in self:
            if not rec.employee_id or not rec.start_datetime:
                rec.weekly_overtime_hours = 0.0
                continue
            week_entries = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('start_datetime', '>=', rec.weekly_start),
                ('start_datetime', '<=', rec.weekly_end),
            ])
            rec.weekly_overtime_hours = sum(week_entries.mapped('daily_overtime_hours'))

    @api.constrains('employee_id', 'start_datetime', 'end_datetime')
    def _check_overtime_overlap(self):
        for rec in self:
            if not rec.start_datetime or not rec.end_datetime:
                continue

            if rec.end_datetime <= rec.start_datetime:
                raise ValidationError("End time must be after start time.")

            # 🔹 Check overlap with normal activities
            normal_overlap = self.env['employee.daily.activity'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('start_datetime', '<', rec.end_datetime),
                ('end_datetime', '>', rec.start_datetime),
            ], limit=1)

            if normal_overlap:
                raise ValidationError(
                    "Overtime cannot overlap with normal working hours."
                )

            # 🔹 Check overlap with other overtime entries
            overtime_overlap = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('id', '!=', rec.id),
                ('start_datetime', '<', rec.end_datetime),
                ('end_datetime', '>', rec.start_datetime),
            ], limit=1)

            if overtime_overlap:
                raise ValidationError(
                    "Overtime overlaps with another overtime entry."
                )

    # -------------------------------
    # Validations
    # -------------------------------
    @api.constrains('daily_overtime_hours')
    def _check_daily_overtime(self):
        for rec in self:
            if rec.daily_overtime_hours < 0:
                raise ValidationError("Daily overtime cannot be negative.")

            # Ensure daily normal hours reach 8 first
            activities = self.env['employee.daily.activity'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('date', '=', rec.start_datetime.date()),
            ])
            total_normal_hours = sum(activities.mapped('time_spent_hours'))

            if total_normal_hours < 8 and rec.daily_overtime_hours > 0:
                raise ValidationError(
                    f"Daily overtime is not allowed. "
                    f"Normal hours ({total_normal_hours}) must reach 8 first."
                )

    # -------------------------------
    # Actions
    # -------------------------------
    def action_confirm(self):
        for rec in self:
            rec.state = 'confirmed'

        # -----------------------

    # Actions
    # -----------------------
    def action_mark_draft(self):
        for rec in self:
            rec.state = 'draft'

        # -------------------------------

    # Prevent Future Overtime Entries
    # -------------------------------
    @api.constrains('start_datetime')
    def _check_no_future_overtime(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.start_datetime:
                overtime_date = rec.start_datetime.date()
                if overtime_date > today:
                    raise ValidationError(
                        "You cannot create overtime for future days."
                    )

    def write(self, vals):
        for rec in self:
            if rec.state == 'confirmed' and not self.env.context.get('bypass_lock'):

                # Allow only state change
                if set(vals.keys()) == {'state'}:
                    continue

                raise ValidationError("Confirmed activities cannot be edited!")

        return super(EmployeeOvertime, self).write(vals)

    def unlink(self):
        for rec in self:
            if rec.state == 'confirmed' and not self.env.context.get('bypass_lock'):
                raise ValidationError("Confirmed activities cannot be deleted!")
        return super(EmployeeOvertime, self).unlink()
