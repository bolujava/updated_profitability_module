# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.osv import expression
from odoo.exceptions import ValidationError, UserError
from odoo.tools.translate import _
from datetime import date, timedelta

_logger = logging.getLogger(__name__)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Sales Order Item',
        help="Sales order item from which this project originates."
    )

    sale_order_id = fields.Many2one(
        related='sale_line_id.order_id',
        string='Sales Order',
        store=True,
        readonly=True
    )


class ProjectTask(models.Model):
    _inherit = 'project.task'

    assigned_employee_ids = fields.Many2many(
        'hr.employee',
        string="Assigned Employee",
        help="assigned to this task"
    )

    # ===== IMPORT HELPER FIELDS (For CSV Bulk Import) =====
    assigned_employee_import = fields.Char(
        string="Assigned Employee",
        help="Use employee name or email for CSV import. Format: 'John Doe' or 'john@example.com'"
    )

    job_rate_import = fields.Char(
        string="Resource Type",
        help="Use job rate name for CSV import. Format: 'Software Engineer' or 'Project Manager'"
    )

    task_starting_date_import = fields.Date(
        string="Task Starting Date",
        help="Helper field for CSV import - Task Starting Date"
    )

    date_deadline_import = fields.Date(
        string="Deadline",
        help="Helper field for CSV import - Task Deadline"
    )

    description_import = fields.Text(
        string="Description",
        help="Helper field for CSV import - Task Description"
    )

    name_import = fields.Char(
        string="Title of Task",
        help="Helper field for CSV import - Task Title/Name"
    )


    @api.model
    def create(self, vals):
        # Put import context to skip validation during import
        ctx = dict(self.env.context)
        if vals.get('assigned_employee_import') or vals.get('name_import'):
            ctx['import_file'] = True

        # Handle task name import
        if vals.get('name_import'):
            vals['name'] = vals.get('name_import')

        # ===== PREVENT DUPLICATES DURING IMPORT =====
        project_id = vals.get('project_id')
        task_name = vals.get('name')

        # Check if we're in an import context and a duplicate task exists
        if project_id and task_name and ctx.get('import_file'):
            existing_task = self.search([
                ('project_id', '=', project_id),
                ('name', '=', task_name)
            ], limit=1)

            if existing_task:
                _logger.info(
                    f"Task '{task_name}' already exists in project. Updating existing task instead of creating duplicate.")
                # Update existing task with new values instead of creating duplicate
                existing_task.write(vals)
                return existing_task
        # ===== END OF DUPLICATE PREVENTION =====

        # Handle assigned employee import
        if vals.get('assigned_employee_import'):
            employee_name = vals.get('assigned_employee_import')
            employee = self.env['hr.employee'].search([
                '|',
                ('name', 'ilike', employee_name),
                ('work_email', 'ilike', employee_name)
            ], limit=1)
            if employee:
                vals['assigned_employee_ids'] = [(6, 0, [employee.id])]
                # Sync to user_id (Odoo's native assignment field)
                if employee.user_id:
                    vals['user_id'] = employee.user_id.id
            else:
                _logger.warning(f"Employee not found for import: {employee_name}")

        # Handle direct user_id assignment (sync to assigned_employee_ids)
        if vals.get('user_id'):
            user = self.env['res.users'].browse(vals.get('user_id'))
            if user and user.employee_id:
                vals['assigned_employee_ids'] = [(6, 0, [user.employee_id.id])]

        # Handle job rate import
        if vals.get('job_rate_import'):
            job_rate_name = vals.get('job_rate_import')
            job_rate = self.env['project.job.rate'].search([
                ('name', 'ilike', job_rate_name)
            ], limit=1)
            if job_rate:
                vals['job_rate_id'] = job_rate.id
            else:
                _logger.warning(f"Job Rate not found for import: {job_rate_name}")

        if vals.get('task_starting_date_import'):
            vals['task_starting_date'] = vals.get('task_starting_date_import')

        if vals.get('date_deadline_import'):
            vals['date_deadline'] = vals.get('date_deadline_import')

        if vals.get('description_import'):
            vals['description'] = vals.get('description_import')

        # task = super(ProjectTask, self.with_context(ctx)).create(vals)
        # if task.assigned_employee_ids:
        #     task._send_task_assignment_notification(task.assigned_employee_ids)
        # return task
        task = super(ProjectTask, self.with_context(ctx)).create(vals)

        # SEND NOTIFICATIONS - ALWAYS (even during bulk import)
        if task.assigned_employee_ids:
            task._send_task_assignment_notification(task.assigned_employee_ids)

        return task

    def write(self, vals):
        # Put import context to skip validation during import
        ctx = dict(self.env.context)
        if vals.get('assigned_employee_import') or vals.get('name_import'):
            ctx['import_file'] = True

        if vals.get('name_import'):
            vals['name'] = vals.get('name_import')

        if vals.get('assigned_employee_import'):
            employee_name = vals.get('assigned_employee_import')
            employee = self.env['hr.employee'].search([
                '|',
                ('name', 'ilike', employee_name),
                ('work_email', 'ilike', employee_name)
            ], limit=1)
            if employee:
                vals['assigned_employee_ids'] = [(6, 0, [employee.id])]
                # Sync to user_id (Odoo's native assignment field)
                if employee.user_id:
                    vals['user_id'] = employee.user_id.id

        # Handle direct user_id assignment (sync to assigned_employee_ids)
        if vals.get('user_id'):
            user = self.env['res.users'].browse(vals.get('user_id'))
            if user and user.employee_id:
                vals['assigned_employee_ids'] = [(6, 0, [user.employee_id.id])]

        if vals.get('job_rate_import'):
            job_rate_name = vals.get('job_rate_import')
            job_rate = self.env['project.job.rate'].search([
                ('name', 'ilike', job_rate_name)
            ], limit=1)
            if job_rate:
                vals['job_rate_id'] = job_rate.id
            else:
                _logger.warning(f"Job Rate not found for import: {job_rate_name}")

        if vals.get('task_starting_date_import'):
            vals['task_starting_date'] = vals.get('task_starting_date_import')

        if vals.get('date_deadline_import'):
            vals['date_deadline'] = vals.get('date_deadline_import')

        if vals.get('description_import'):
            vals['description'] = vals.get('description_import')

        # Store old assignees BEFORE any changes (critical for detecting new assignments during import)
        old_assignee_map = {}
        for task in self:
            old_assignee_map[task.id] = task.assigned_employee_ids.ids

        res = super(ProjectTask, self.with_context(ctx)).write(vals)

        # SEND NOTIFICATIONS - ALWAYS (even during bulk import)
        for task in self:
            old_ids = old_assignee_map.get(task.id, [])
            new_assignees = task.assigned_employee_ids.filtered(lambda emp: emp.id not in old_ids)
            if new_assignees:
                task._send_task_assignment_notification(new_assignees)

        return res

    def _send_task_assignment_notification(self, employee_records):
        for task in self:
            for employee in employee_records:
                if not employee.work_email:
                    _logger.warning(f"Skipped task alert for {employee.name}: No email address found.")
                    continue
                try:
                    base_url = task.project_id._get_base_url() if task.project_id else False

                    if not base_url:
                        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

                    if base_url:
                        base_url = base_url.strip().rstrip('/')
                    else:
                        _logger.error(
                            "Production Alert: 'web.base.url' parameter is missing from your Odoo Settings table!")

                except Exception as e:
                    _logger.error(f"Critical error fetching application domain parameter: {str(e)}")
                    continue

                subject = f"New Task Assignment: '{task.name}'"
                body_html = f"""
                    <p>Hello {employee.name},</p>
                    <p>You have been assigned to the following task:</p>
                    <ul>
                        <li><strong>Task Name:</strong> {task.name}</li>
                        <li><strong>Project:</strong> {task.project_id.name if task.project_id else 'N/A'}</li>
                        <li><strong>Start Date:</strong> {task.task_starting_date if task.task_starting_date else 'Not Set'}</li>
                        <li><strong>Deadline:</strong> {task.date_deadline if task.date_deadline else 'No Deadline'}</li>
                    </ul>
                    <p>Start logging your time via the Employee Daily Tracker Activities Module application</p>
                    <p style="margin-top: 20px;">
                        <a href="{base_url}/web#id={task.id}&model=project.task&view_type=form"
                           style="padding: 10px 15px; background-color: #7C5BBA; text-decoration: none; color: #fff; border-radius: 4px; font-weight: bold;">
                           View Task Details
                        </a>
                    </p>
                """

                try:
                    task.env['mail.mail'].sudo().create({
                        'subject': subject,
                        'body_html': body_html,
                        'email_to': employee.work_email,
                    }).send()
                    _logger.info(f"Task assignment email successfully dispatched to {employee.work_email}")
                except Exception as e:
                    _logger.error(f"Failed to send task assignment email to {employee.work_email}: {str(e)}")

    # ===== BIDIRECTIONAL SYNC BETWEEN assigned_employee_ids AND user_id =====

    @api.depends('assigned_employee_ids')
    def _compute_user_id_from_employee(self):
        """Sync assigned_employee_ids (hr.employee) to user_id (res.users)"""
        for task in self:
            employee = task.assigned_employee_ids[:1] if task.assigned_employee_ids else False
            if employee and employee.user_id:
                task.user_id = employee.user_id.id
            else:
                task.user_id = False

    # Override the native user_id field to be computed but also writable
    user_id = fields.Many2one(
        'res.users',
        string="Assigned to",
        compute='_compute_user_id_from_employee',
        store=True,
        readonly=False,
        help="User assigned to this task (synced with assigned_employee_ids)"
    )

    # ===== END OF BIDIRECTIONAL SYNC =====

    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Sales Order Item',
        compute='_compute_sale_line_id',
        store=True,
        readonly=False,
        help="Sales order item linked through the project."
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        compute='_compute_sale_line_id',
        store=True,
        readonly=False
    )

    job_rate_id = fields.Many2one(
        'project.job.rate',
        string="Resource Type",
        required=True,
        help="Job rate for this task - all assigned employees inherit this rate"
    )

    average_timesheet_hours = fields.Float(
        string="Average Timesheet Hours",
        compute="_compute_timesheet_totals",
        store=True
    )

    total_timesheet_hours = fields.Float(
        string="Average Timesheet Hours",
        compute="_compute_timesheet_totals",
        store=True
    )

    @api.depends('timesheet_ids.unit_amount', 'assigned_employee_ids', 'sale_line_id')
    def _compute_timesheet_totals(self):
        for task in self:
            timesheets = task.timesheet_ids
            if not task.job_rate_id or 'consultant' not in task.job_rate_id.name.lower():
                timesheets = timesheets.filtered(lambda ts: ts.employee_id in task.assigned_employee_ids)

            total_hours = sum(timesheets.mapped('unit_amount'))
            employee_count = len(task.assigned_employee_ids) or 1
            task.total_timesheet_hours = total_hours
            task.average_timesheet_hours = total_hours / employee_count if employee_count > 0 else 0.0

            if task.sale_line_id:
                task.sale_line_id._compute_delivered_from_tasks()
                if task.project_id:
                    task.project_id._compute_profitability()

    @api.depends('project_id.sale_line_id')
    def _compute_sale_line_id(self):
        for task in self:
            if task.project_id and task.project_id.sale_line_id:
                task.sale_line_id = task.project_id.sale_line_id
                task.sale_order_id = task.project_id.sale_order_id
            else:
                task.sale_line_id = False
                task.sale_order_id = False

    planned_hours = fields.Float(
        string="Planned Hours",
        compute="_compute_planned_hours",
        store=True,
        readonly=False,
        track=True,
        help="Calculated automatically as the working hours between the starting date and deadline date."
    )

    task_starting_date = fields.Date(string="Task Starting Date")

    @api.depends('task_starting_date', 'date_deadline')
    def _compute_planned_hours(self):
        for task in self:
            if not task.task_starting_date or not task.date_deadline:
                task.planned_hours = 0.0
                continue

            calendar = (
                    task.project_id.company_id.resource_calendar_id
                    or task.company_id.resource_calendar_id
            )

            if not calendar:
                task.planned_hours = 0.0
                continue

            start_dt = fields.Datetime.to_datetime(task.task_starting_date)
            end_dt = fields.Datetime.to_datetime(task.date_deadline) + timedelta(days=1, seconds=-1)

            if start_dt < end_dt:
                working_hours = calendar.get_work_hours_count(
                    start_dt,
                    end_dt,
                    compute_leaves=True
                )
                task.planned_hours = working_hours
            else:
                task.planned_hours = 0.0

    @api.constrains('task_starting_date', 'date_deadline')
    def _check_start_date_vs_deadline(self):
        for task in self:
            if task.task_starting_date and task.date_deadline:
                start_date = fields.Date.to_string(task.task_starting_date) if isinstance(task.task_starting_date,
                                                                                          date) else task.task_starting_date
                deadline = fields.Date.to_string(task.date_deadline) if isinstance(task.date_deadline,
                                                                                   date) else task.date_deadline

                if task.task_starting_date > task.date_deadline:
                    raise ValidationError(
                        "❌ Invalid dates!\n"
                        f"Task starting date ({start_date}) cannot be later than or equal to the deadline ({deadline}).\n"
                        "Please set a starting date that comes before the deadline."
                    )

    @api.constrains('assigned_employee_ids')
    def _check_single_assignee_restriction(self):
        # Skip validation during import/load operations
        if self.env.context.get('import_file') or self.env.context.get('load_data'):
            return

        for task in self:
            if len(task.assigned_employee_ids) > 1:
                raise ValidationError(
                    "❌ Strict Assignment Restriction!\n\n"
                    f"Task '{task.name}' cannot have multiple assignees. "
                    f"You have selected {len(task.assigned_employee_ids)} employees. "
                    "Please assign exactly one person to this task before saving."
                )

            if not task.assigned_employee_ids and (task.name or task.project_id):
                raise ValidationError(
                    "❌ Task Assignment Required!\n\n"
                    "You must assign exactly one person to this task before it can be saved."
                )


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    employee_type = fields.Selection(
        selection=[
            ('technical', 'Technical'),
            ('non_technical', 'Non-Technical'),
            ('employee', 'Employee')
        ],
        string="Employee Type",
        readonly=True,
    )

    timesheet_cost = fields.Float(
        string="Timesheet Cost",
        readonly=True
    )

    team_lead_id = fields.Many2one(
        'hr.employee',
        string='Team Lead',
        readonly=True,
    )

    profitability_score = fields.Float(
        string="Performance Efficiency (%)",
        readonly=True,
        store=False
    )

    selling_price_per_hour = fields.Float(
        string="Selling Price/Hour",
        readonly=True,
        store=False
    )

    cost_per_hour = fields.Float(
        string="Cost/Hour",
        readonly=True,
        store=False
    )

    total_hours = fields.Float(
        string="Total Hours (Timesheet)",
        readonly=True,
        store=False
    )

    total_revenue = fields.Float(
        string="Total Revenue",
        readonly=True,
        store=False
    )

    total_cost = fields.Float(
        string="Total Cost",
        readonly=True,
        store=False
    )

    total_profit = fields.Float(
        string="Profit",
        readonly=True,
        store=False
    )

    profit_margin = fields.Float(
        string="Profit Margin (%)",
        readonly=True,
        store=False
    )

    def _compute_public_employee_fields(self):
        try:
            real_employees = self.env['hr.employee'].sudo().browse(self.ids)
            employee_dict = {emp.id: emp for emp in real_employees}

            for public in self:
                real = employee_dict.get(public.id)

                if real:
                    public.employee_type = getattr(real, 'employee_type', 'employee') or 'employee'
                    public.timesheet_cost = getattr(real, 'timesheet_cost', 0.0) or 0.0
                    team_lead = getattr(real, 'team_lead_id', False)
                    public.team_lead_id = team_lead.id if team_lead else False
                    public.profitability_score = getattr(real, 'profitability_score', 0.0) or 0.0
                    public.selling_price_per_hour = getattr(real, 'selling_price_per_hour', 0.0) or 0.0
                    public.cost_per_hour = getattr(real, 'cost_per_hour', 0.0) or 0.0
                    public.total_hours = getattr(real, 'total_hours', 0.0) or 0.0
                    public.total_revenue = getattr(real, 'total_revenue', 0.0) or 0.0
                    public.total_cost = getattr(real, 'total_cost', 0.0) or 0.0
                    public.total_profit = getattr(real, 'total_profit', 0.0) or 0.0
                    public.profit_margin = getattr(real, 'profit_margin', 0.0) or 0.0

                else:
                    public.employee_type = 'employee'
                    public.timesheet_cost = 0.0
                    public.team_lead_id = False
                    public.profitability_score = 0.0
                    public.selling_price_per_hour = 0.0
                    public.cost_per_hour = 0.0
                    public.total_hours = 0.0
                    public.total_revenue = 0.0
                    public.total_cost = 0.0
                    public.total_profit = 0.0
                    public.profit_margin = 0.0

        except Exception as e:
            _logger.error(f"Error in _compute_public_employee_fields: {str(e)}")
            for public in self:
                public.employee_type = 'employee'
                public.timesheet_cost = 0.0
                public.team_lead_id = False
                public.profitability_score = 0.0
                public.selling_price_per_hour = 0.0
                public.cost_per_hour = 0.0
                public.total_hours = 0.0
                public.total_revenue = 0.0
                public.total_cost = 0.0
                public.total_profit = 0.0
                public.profit_margin = 0.0

    @api.model
    def sync_from_hr_employee(self, employee_ids=None):
        if employee_ids:
            records = self.browse(employee_ids)
        else:
            records = self.search([])
        records._compute_public_employee_fields()
        return True