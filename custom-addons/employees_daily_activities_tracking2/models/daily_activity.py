from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime, time


class EmployeeDailyActivity(models.Model):
    _name = 'employee.daily.activity'
    _description = 'Employee Daily Activity'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_datetime desc'

    # -----------------------
    # Basic Info
    # -----------------------
    name = fields.Char(
        string="Activity Summary",
        compute="_compute_name",
        store=True,
        tracking=True
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        required=True,
        default=lambda self: self._default_employee(),
        tracking=True
    )

    department_id = fields.Many2one(
        'hr.department',
        string="Department",
        compute="_compute_department",
        store=True
    )

    parent_id = fields.Many2one(
        'hr.employee',
        string="Department Manager",
        compute='_compute_manager',
        store=True
    )

    @api.depends('employee_id')
    def _compute_manager(self):
        for rec in self:
            rec.parent_id = rec.employee_id.parent_id

    team_lead_id = fields.Many2one(
        'hr.employee',
        string="Team Lead",
        compute='_compute_team',
        store=True
    )

    @api.depends('employee_id')
    def _compute_team(self):
        for rec in self:
            rec.team_lead_id = rec.employee_id.team_lead_id

    employee_type = fields.Selection(
        [('technical', 'Technical'), ('non_technical', 'Non-Technical')],
        string="Employee Type",
        compute="_compute_employee_type",
        store=True
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

    time_spent_hours = fields.Float(
        string="Time Spent (Hours)",
        compute="_compute_time_spent",
        store=True
    )

    description = fields.Text(string="Work Description", required=True)

    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed')],
        default='draft',
        tracking=True
    )

    training_code = fields.Char(
        string="Training Code",
        related='training_attendee_id.training_code',
        store=True,
        readonly=True
    )

    # -----------------------
    # Activity Type & Dynamic Records
    # -----------------------
    custom_activity_type_id = fields.Many2one(
        'activity.type',
        string="Activity Type",
        required=True,
        domain="[('department_ids', 'in', department_id)]",
        tracking=True
    )

    activity_name = fields.Char(
        string="Activity Name",
        related='custom_activity_type_id.name',
        readonly=True
    )

    activity_res_model = fields.Char(
        related='custom_activity_type_id.res_model',
        store=False,
        readonly=True
    )

    # Links
    helpdesk_ticket_id = fields.Many2one('helpdesk.ticket', string="Support Activity:")

    project_id = fields.Many2one('project.project', string="Project Activity:")
    crm_opportunity_id = fields.Many2one('crm.lead', string="Pre-Sales Activity:")
    training_attendee_id = fields.Many2one(
        'training.course',
        string="Training Activity"
    )

    @api.constrains('custom_activity_type_id', 'helpdesk_ticket_id', 'project_id', 'crm_opportunity_id',
                    'training_attendee_id')
    def _check_activity_required_fields(self):
        for rec in self:
            model = rec.custom_activity_type_id.res_model if rec.custom_activity_type_id else False
            if model == 'helpdesk.ticket' and not rec.helpdesk_ticket_id:
                raise ValidationError("Support Activity must be set for this activity type.")
            elif model == 'project.project' and not rec.project_id:
                raise ValidationError("Project Activity must be set for this activity type.")
            elif model == 'crm.lead' and not rec.crm_opportunity_id:
                raise ValidationError("Pre-Sales Activity must be set for this activity type.")
            elif model == 'training.course' and not rec.training_attendee_id:
                raise ValidationError("Training Activity must be set for this activity type.")

    # -----------------------
    # Metadata
    # -----------------------
    date = fields.Date(string="Date", compute="_compute_date", store=True)
    year = fields.Integer(string="Year", store=True, tracking=True)
    quarter = fields.Selection(
        [('q1', 'Quarter 1'), ('q2', 'Quarter 2'), ('q3', 'Quarter 3'), ('q4', 'Quarter 4')],
        string="Quarter",
        compute="_compute_quarter",
        store=True,
        tracking=True
    )

    res_model = fields.Char(
        string="Related Model",
        default='employee.daily.activity',
        readonly=True
    )

    # -----------------------
    # Default Methods
    # -----------------------
    def _default_employee(self):
        return self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)

    # -----------------------
    # Computes
    # -----------------------
    @api.depends('employee_id')
    def _compute_department(self):
        for rec in self:
            rec.department_id = rec.employee_id.department_id

    @api.depends('department_id')
    def _compute_employee_type(self):
        for rec in self:
            if rec.department_id.is_technical:
                rec.employee_type = 'technical'
            elif rec.department_id.is_non_technical:
                rec.employee_type = 'non_technical'
            else:
                rec.employee_type = False

    @api.depends('employee_id', 'start_datetime')
    def _compute_name(self):
        for rec in self:
            emp = rec.employee_id.name or 'Employee'
            date_str = rec.start_datetime.date() if rec.start_datetime else ''
            rec.name = f"{emp} - {date_str}"

    @api.depends('start_datetime', 'end_datetime')
    def _compute_time_spent(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime:
                delta = rec.end_datetime - rec.start_datetime
                rec.time_spent_hours = delta.total_seconds() / 3600
            else:
                rec.time_spent_hours = 0.0

    @api.depends('start_datetime')
    def _compute_date(self):
        for rec in self:
            rec.date = rec.start_datetime.date() if rec.start_datetime else False

    @api.depends('start_datetime')
    def _compute_quarter(self):
        for rec in self:
            if rec.start_datetime:
                month = rec.start_datetime.month
                if month <= 3:
                    rec.quarter = 'q1'
                elif month <= 6:
                    rec.quarter = 'q2'
                elif month <= 9:
                    rec.quarter = 'q3'
                else:
                    rec.quarter = 'q4'
                rec.year = rec.start_datetime.year
            else:
                rec.quarter = False
                rec.year = False

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

    # -----------------------
    # Actions
    # -----------------------
    def action_confirm(self):
        self.write({'state': 'confirmed'})

        # -----------------------

    # Actions
    # -----------------------
    def action_mark_draft(self):
        for rec in self:
            rec.state = 'draft'

    def write(self, vals):
        for rec in self:
            if rec.state == 'confirmed' and not self.env.context.get('bypass_lock'):

                # Allow only state change
                if set(vals.keys()) == {'state'}:
                    continue

                raise ValidationError("Confirmed activities cannot be edited!")

        return super(EmployeeDailyActivity, self).write(vals)

    def unlink(self):
        for rec in self:
            if rec.state == 'confirmed' and not self.env.context.get('bypass_lock'):
                raise ValidationError("Confirmed activities cannot be deleted!")
        return super(EmployeeDailyActivity, self).unlink()

    @api.constrains('employee_id', 'start_datetime', 'end_datetime')
    def _check_overlap(self):
        for rec in self:
            if not rec.start_datetime or not rec.end_datetime:
                continue
            overlapping = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('id', '!=', rec.id),
                ('start_datetime', '<', rec.end_datetime),
                ('end_datetime', '>', rec.start_datetime),
            ])
            if overlapping:
                raise ValidationError(f"Activity overlaps with another activity for {rec.employee_id.name}.")

    @api.constrains('employee_id', 'start_datetime', 'end_datetime', 'time_spent_hours')
    def _check_daily_hours(self):
        for rec in self:
            if not rec.start_datetime or not rec.end_datetime:
                continue
            activities = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('id', '!=', rec.id),
                ('date', '=', rec.start_datetime.date()),
            ])
            total_hours = sum(activities.mapped('time_spent_hours')) + rec.time_spent_hours
            if total_hours > 8:
                raise ValidationError(
                    f"Daily limit exceeded for {rec.employee_id.name}. Total hours ({total_hours}) > 8.")

    @api.constrains('employee_id', 'start_datetime', 'end_datetime', 'time_spent_hours')
    def _check_weekly_hours(self):
        for rec in self:
            if not rec.start_datetime or not rec.end_datetime:
                continue
            iso_year, iso_week, iso_weekday = rec.start_datetime.isocalendar()
            activities = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('id', '!=', rec.id),
                ('start_datetime', '>=', rec.start_datetime - timedelta(days=iso_weekday - 1)),
                ('start_datetime', '<=', rec.start_datetime + timedelta(days=7 - iso_weekday)),
            ])
            total_hours = sum(activities.mapped('time_spent_hours')) + rec.time_spent_hours
            if total_hours > 40:
                raise ValidationError(
                    f"Weekly limit exceeded for {rec.employee_id.name}. Total hours ({total_hours}) > 40.")

    @api.constrains('start_datetime')
    def _check_activity_date_rules(self):
        today = fields.Date.context_today(self)

        for rec in self:
            if not rec.start_datetime:
                continue

            activity_date = rec.start_datetime.date()
            activity_weekday = activity_date.weekday()  # Mon=0 ... Sun=6

            # 1️⃣ Only Monday–Friday
            if activity_weekday > 4:
                raise ValidationError(
                    "Activities can only be created from Monday to Friday."
                )

            # 2️⃣ No future days
            if activity_date > today:
                raise ValidationError(
                    "You cannot create activities for future days."
                )

            # 3️⃣ Lock previous week after Saturday 00:00
            today_week = today.isocalendar()[1]
            activity_week = activity_date.isocalendar()[1]

            now = fields.Datetime.context_timestamp(self, datetime.now())

            if now.weekday() == 5:  # Saturday
                saturday_midnight = datetime.combine(today, time.min)
                saturday_midnight = fields.Datetime.context_timestamp(self, saturday_midnight)

                if now >= saturday_midnight and activity_week < today_week:
                    raise ValidationError(
                        "Last week's activities are locked after Saturday."
                    )


class ActivityType(models.Model):
    _name = 'activity.type'
    _description = 'Activity Type'

    name = fields.Char(string='Activity Name', required=True)
    code = fields.Char(string='Code', help="Optional internal code")
    res_model = fields.Char(string='Related Model')

    department_ids = fields.Many2many(
        'hr.department',
        string='Allowed Departments',
        required=True
    )