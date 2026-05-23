# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.osv import expression
from odoo.exceptions import ValidationError, UserError
from odoo.tools.translate import _
from datetime import date, timedelta

_logger = logging.getLogger(__name__)


class ProjectEnhancement(models.Model):
    _inherit = 'project.project'

    name = fields.Char('Name', required=True)
    pmo = fields.Many2one(
        'hr.employee', string='PMO',
        default=lambda self: self._get_pmo()
    )
    display_planning_timesheet_analysis = fields.Boolean(
        string="Display Planning Timesheet Analysis",
        default=False
    )
    avg_employee_profitability = fields.Float(
        string="Average Employee Profitability (%)",
        compute="_compute_employee_profitability_score",
        store=False,
    )
    allocated_hours = fields.Float(string="Allocated Hours", compute="_compute_allocated_hours", store=True,
                                   tracking=True)

    project_progress = fields.Float(
        string="Project Progress (%)",
        compute='_compute_project_progress',
        store=True,
        groups="project.group_project_manager",
        digits=(16, 2)
    )

    # total_project = fields.Integer(string="Total active Projects", compute="_compute_total_project")

    @api.depends('task_ids.progress')
    def _compute_project_progress(self):
        """Calculates the project's overall progress by averaging the progress of all associated tasks."""
        for project in self:
            # Filter for tasks that have a progress value to be included in the average.
            # You might adjust this filter based on task stages you want to exclude (e.g., cancelled).
            tasks = project.task_ids.filtered(lambda t: t.progress > 0.0 or t.stage_id.fold is False)

            if tasks:
                # Calculate the simple average of all task progress percentages
                total_progress = sum(tasks.mapped('progress'))
                project.project_progress = total_progress / len(tasks)
            else:
                project.project_progress = 0.0

    @api.depends('date_start', 'date')  # <-- CORRECTED: Now depends on 'date_start' and 'date'
    def _compute_allocated_hours(self):
        for project in self:
            allocated_hours = 0.0

            if project.date_start and project.date:
                calendar = project.company_id.resource_calendar_id

                start_dt = fields.Datetime.to_datetime(project.date_start)
                end_dt = fields.Datetime.to_datetime(project.date) + timedelta(days=1, seconds=-1)

                if calendar:
                    allocated_hours = calendar.get_work_hours_count(
                        start_dt,
                        end_dt,
                        compute_leaves=True
                    )

            project.allocated_hours = allocated_hours

    # You may also want to update your date constraint to use the correct fields:
    @api.constrains('date_start', 'date')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date and rec.date_start > rec.date:
                raise ValidationError("End Date must be after Start Date.")

    # This is what I have

    starting_date = fields.Date(string="Starting Date")
    ending_date = fields.Date(string="Ending Date")

    department_id = fields.Many2one('hr.department', string='Department')
    department_manager_id = fields.Many2one(
        'hr.employee', string='Department Manager',
        domain="[('department_id', '=', department_id)]",
        compute="_compute_department_manager", store=True, readonly=False  # CHANGED: readonly=False to allow tracking
    )
    team_lead_id = fields.Many2one(
        'hr.employee',
        string='Team Lead',
        domain="[('department_id', '=', department_id)]",
    )

    project_manager = fields.Many2one(
        'hr.employee', string='Project Manager',
        domain="[('department_id', '=', 5)]"
    )

    status = fields.Selection([
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('deprioritized', 'De-prioritized'),
        ('closed', 'Closed'),
    ], default='active', required=True)

    current_user_id = fields.Many2one(
        'res.users', compute="_compute_current_user", store=False
    )

    # Budget Fields
    # currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id.id,
        readonly=True  # Or set based on project configuration
    )
    # currency_symbol = fields.Char(related='currency_id.symbol')

    budget = fields.Monetary(
        string='Budget',
        compute='_compute_budget_from_so',
        store=True,
        readonly=False,
        tracking=True,
        help="Automatically set from the total amount of the confirmed "
             "Sales Order linked to this project.",
    )
    budget_utilized = fields.Monetary(string='Budget Utilized', compute='_compute_budget_utilized', store=True)
    budget_remaining = fields.Monetary(string='Remaining Budget', compute='_compute_budget_remaining', store=True)
    profitability = fields.Monetary(string='Profitability', compute='_compute_profitability', store=True)
    forecasted_budget_overrun = fields.Monetary(string='Forecasted Budget Overrun',
                                                compute='_compute_forecasted_overrun', store=True)
    budget_alert_threshold = fields.Float(string="Budget Alert Threshold (%)", default=80.0)
    budget_alert_sent = fields.Boolean(string='Budget Alert Sent', default=False)
    budget_utilization = fields.Float(
        string='Budget Utilization (%)',
        compute='_compute_budget_utilization',
        store=True,
        help="How much of the total budget has been spent, as a percentage."
    )

    budget_status = fields.Selection(
        [
            ('safe', 'Safe'),
            ('warning', 'Approaching Limit'),
            ('exceeded', 'Exceeded'),
        ],
        string='Budget Status',
        compute='_compute_budget_utilization',
        store=True,
        help="Visual indicator for how the project is tracking against its budget."
    )

    # NEW: Fixed write method - REPLACE your existing write method with this one
    def write(self, vals):
        # Capture existing values BEFORE the write
        old_values = {}
        for rec in self:
            old_values[rec.id] = {
                'project_manager': rec.project_manager.id if rec.project_manager else False,
                'department_id': rec.department_id.id if rec.department_id else False,
                'department_manager_id': rec.department_manager_id.id if rec.department_manager_id else False,
                'team_lead_id': rec.team_lead_id.id if rec.team_lead_id else False,
            }
            _logger.info(
                f"📋 OLD VALUES for '{rec.name}': PM={old_values[rec.id]['project_manager']}, Dept={old_values[rec.id]['department_id']}, DeptMgr={old_values[rec.id]['department_manager_id']}, TeamLead={old_values[rec.id]['team_lead_id']}")

        # Execute the write operation
        res = super(ProjectEnhancement, self).write(vals)

        # Send notifications for changes AFTER the write
        for rec in self:
            # Refresh to get computed values
            rec.refresh()

            old = old_values.get(rec.id, {})

            new_pm = rec.project_manager.id if rec.project_manager else False
            new_dept_id = rec.department_id.id if rec.department_id else False
            new_dept_mgr = rec.department_manager_id.id if rec.department_manager_id else False
            new_team_lead = rec.team_lead_id.id if rec.team_lead_id else False

            _logger.info(
                f"📋 NEW VALUES for '{rec.name}': PM={new_pm}, Dept={new_dept_id}, DeptMgr={new_dept_mgr}, TeamLead={new_team_lead}")

            # 1. Check Project Manager
            if new_pm != old.get('project_manager'):
                _logger.info(f"🎯 Project Manager CHANGED!")
                if new_pm and rec.project_manager:
                    rec._send_role_assignment_notification('project_manager', rec.project_manager)

            # 2. Check Department Manager (when department changes OR when department manager changes)
            dept_changed = new_dept_id != old.get('department_id')
            dept_mgr_changed = new_dept_mgr != old.get('department_manager_id')

            if dept_changed or dept_mgr_changed:
                _logger.info(
                    f"🎯 Department Manager CHANGED! (Dept changed: {dept_changed}, Mgr changed: {dept_mgr_changed})")
                if new_dept_mgr and rec.department_manager_id:
                    rec._send_role_assignment_notification('department_manager', rec.department_manager_id)

            # 3. Check Team Lead
            if new_team_lead != old.get('team_lead_id'):
                _logger.info(f"🎯 Team Lead CHANGED!")
                if new_team_lead and rec.team_lead_id:
                    rec._send_role_assignment_notification('team_lead', rec.team_lead_id)

        return res

    # REPLACE your existing create method with this one
    @api.model
    def create(self, vals):
        _logger.info("=" * 60)
        _logger.info(f"🆕 CREATING NEW PROJECT")

        vals.setdefault('pmo', self._get_pmo())

        if 'department_id' in vals:
            department = self.env['hr.department'].browse(vals['department_id'])
            vals['department_manager_id'] = department.manager_id.id if department.manager_id else False
            _logger.info(f"Setting department_manager_id to: {vals['department_manager_id']}")

        project = super().create(vals)
        _logger.info(f"Project created: {project.name} (ID: {project.id})")

        if project.sale_order_id and project.sale_order_id.project_document_link:
            project.document_upload_link = project.sale_order_id.project_document_link
            _logger.info(f"Synced Teams link from SO")

        # Set initial role statuses and send notifications
        _logger.info("📧 Sending role assignment notifications...")

        if project.team_lead_id:
            project.team_lead_status = 'pending'
            project._send_role_assignment_notification('team_lead', project.team_lead_id)

        if project.department_manager_id:
            project.department_manager_status = 'pending'
            project._send_role_assignment_notification('department_manager', project.department_manager_id)

        if project.project_manager:
            project.project_manager_status = 'pending'
            project._send_role_assignment_notification('project_manager', project.project_manager)

        # Send project creation email to PMO
        if project.pmo:
            self._send_project_creation_email(project)

        _logger.info("=" * 60)
        return project

    @api.depends('budget', 'budget_utilized', 'budget_alert_threshold')
    def _compute_budget_utilization(self):
        for project in self:
            if project.budget:
                utilization = (project.budget_utilized / project.budget) * 100
                project.budget_utilization = utilization

                if utilization >= project.budget_alert_threshold:
                    project.budget_status = 'exceeded'
                elif utilization >= (project.budget_alert_threshold * 0.8):
                    project.budget_status = 'warning'
                else:
                    project.budget_status = 'safe'
            else:
                project.budget_utilization = 0.0
                project.budget_status = 'safe'

    # Logs & Relations
    change_log_ids = fields.One2many('project.change.log', 'project_id', string="Change Logs", readonly=True)
    task_ids = fields.One2many('project.task', 'project_id', string='Tasks')
    task_names = fields.Char(string="Task Names", compute="_compute_task_names", store=True)
    expense_ids = fields.One2many('hr.expense', 'project_id', readonly=True, store=True)
    activity_ids = fields.One2many('mail.activity', 'res_id', domain=lambda self: [('res_model', '=', self._name)],
                                   string='Activities', auto_join=True)
    is_edit_mode = fields.Boolean(default=False)

    # Role Statuses
    project_manager_status = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ], string='Project Manager Status')

    team_lead_status = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ], string='Team Lead Status')

    department_manager_status = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ], string='Department Manager Status')

    # Role Acceptance Buttons Visibility
    can_accept_team_lead = fields.Boolean(compute='_check_user_role')
    can_accept_project_manager = fields.Boolean(compute='_check_user_role')
    can_accept_department_manager = fields.Boolean(compute='_check_user_role')

    can_edit_project_manager = fields.Boolean(string='Can Edit Project Manager', compute='_compute_role_edit_rights')
    can_edit_team_lead = fields.Boolean(string='Can Edit Team Lead', compute='_compute_role_edit_rights')
    can_edit_department_manager = fields.Boolean(string='Can Edit Department Manager',
                                                 compute='_compute_role_edit_rights')
    can_edit_pmo = fields.Boolean(string='Can Edit PMO', compute='_compute_role_edit_rights')

    @api.depends_context('uid')
    def _compute_role_edit_rights(self):
        user = self.env.user

        is_pm = user.has_group('lba_profitability_module.group_project_manager')
        is_team_lead = user.has_group('lba_profitability_module.group_team_lead')
        is_dept_manager = user.has_group('lba_profitability_module.group_department_manager')
        is_pmo = user.has_group('lba_profitability_module.group_pmo')

        for project in self:
            project.can_edit_pmo = is_pmo

            project.can_edit_project_manager = (
                    is_pm and
                    project.project_manager and
                    project.project_manager.sudo().user_id.id == user.id and
                    project.project_manager_status == 'accepted'
            )

            project.can_edit_department_manager = (
                    is_dept_manager and
                    project.department_manager_id and
                    project.department_manager_id.sudo().user_id.id == user.id and
                    project.department_manager_status == 'accepted'
            )

            project.can_edit_team_lead = (
                    is_team_lead and
                    project.team_lead_id and
                    project.team_lead_id.sudo().user_id.id == user.id and
                    project.team_lead_status == 'accepted'
            )

    @api.depends_context('uid')
    def _compute_current_user(self):
        for rec in self:
            rec.current_user_id = self.env.user

    @api.depends('department_id')
    def _compute_department_manager(self):
        for rec in self:
            old_mgr = rec.department_manager_id.id if rec.department_manager_id else False
            if rec.department_id and rec.department_id.manager_id:
                rec.department_manager_id = rec.department_id.manager_id
                new_mgr = rec.department_manager_id.id if rec.department_manager_id else False
                if old_mgr != new_mgr and new_mgr:
                    _logger.info(f"🔄 Department Manager auto-assigned: {rec.department_manager_id.name}")
            else:
                rec.department_manager_id = False

    @api.constrains('starting_date', 'ending_date')
    def _check_dates(self):
        for rec in self:
            if rec.starting_date and rec.ending_date and rec.starting_date > rec.ending_date:
                raise ValidationError("End Date must be after Start Date.")

    @api.depends(
        'project_manager_status',
        'team_lead_status',
        'department_manager_status',
        'current_user_id',
        'project_manager.user_id',
        'team_lead_id.user_id',
        'department_manager_id.user_id',
    )
    def _check_user_role(self):
        for rec in self:
            user = rec.current_user_id

            rec.can_accept_project_manager = (
                    rec.project_manager_status == 'pending'
                    and rec.project_manager
                    and rec.project_manager.sudo().user_id == user
            )

            rec.can_accept_team_lead = (
                    rec.team_lead_status == 'pending'
                    and rec.team_lead_id
                    and rec.team_lead_id.sudo().user_id == user
            )

            rec.can_accept_department_manager = (
                    rec.department_manager_status == 'pending'
                    and rec.department_manager_id
                    and rec.department_manager_id.sudo().user_id == user
            )

    @api.depends('task_ids', 'task_ids.name')
    def _compute_task_names(self):
        for rec in self:
            rec.task_names = ', '.join(rec.task_ids.mapped('name'))

    def _update_status_fields(self):
        for record in self:
            if record.project_manager and not record.project_manager_status:
                record.project_manager_status = 'pending'

            if record.team_lead_id and not record.team_lead_status:
                record.team_lead_status = 'pending'

            if record.department_manager_id and not record.department_manager_status:
                record.department_manager_status = 'pending'

            if not record.name:
                raise UserError(_("Name field cannot be empty!"))

    decline_reason = fields.Text('Decline Reason', help="Reason for declining the role.")

    @api.onchange('project_manager')
    def _onchange_project_manager(self):
        if self.project_manager:
            manager_name = self.project_manager.sudo().name
            return {
                'warning': {
                    'title': "Confirm Assignment",
                    'message': f"Are you sure you want to assign {manager_name} as Project Manager?",
                }
            }

    @api.onchange('department_id')
    def _onchange_department_id(self):
        """When department changes, log for notification"""
        if self.department_id and self.department_id.manager_id:
            _logger.info(f"🔄 Department changed to: {self.department_id.name}")
            _logger.info(f"   Department Manager: {self.department_id.manager_id.name}")

    @api.depends('department_id')
    def _compute_team_lead_project(self):

        for project in self:
            if project.department_id and project.department_id.team_lead_id:
                project.team_lead_id = project.department_id.team_lead_id
            else:
                project.team_lead_id = False

    def _inverse_team_lead_project(self):

        for project in self:
            # Explicitly assign the field to its current value to trigger the database write layer
            project.team_lead_id = project.team_lead_id

    @api.onchange('department_manager_id')
    def _onchange_department_manager(self):
        if self.department_manager_id:
            departmental_manager_name = self.department_manager_id.sudo().name
            return {
                'warning': {
                    'title': "Confirm Assignment",
                    'message': f"Are you sure you want to assign {departmental_manager_name} as Department Manager?",
                }
            }

    total_hours = fields.Float(string="Total Expected Hours", compute="_compute_profitability", store=True)
    total_revenue = fields.Float(string="Total Selling Price", compute="_compute_profitability", store=True)
    total_cost = fields.Float(string="Total Internal Cost Price", compute="_compute_profitability", store=True)
    profit = fields.Float(string="Profit", compute="_compute_profitability", store=True)
    profit_margin = fields.Float(string="Profit Margin (%)", compute="_compute_profitability", store=True)
    total_profit = fields.Float(string="Total Profit", compute="_compute_profitability", store=True)
    total_expenses = fields.Float(string="Other Expenses", compute="_compute_total_expenses", store=True)
    resource_profit_ids = fields.One2many(
        'project.resource.profit', 'project_id',
        string='Per-resource Profitability', copy=False
    )

    total_project_cost = fields.Monetary(
        string="Total Project Cost",
        compute="_compute_total_project_cost",
        store=True,
        currency_field='currency_id'
    )

    @api.depends('total_cost', 'total_expenses')
    def _compute_total_project_cost(self):
        for project in self:
            project.total_project_cost = (project.total_cost or 0.0) + (project.total_expenses or 0.0)

    @api.depends('analytic_account_id.line_ids.amount', 'expense_ids.total_amount', 'expense_ids.state')
    def _compute_total_expenses(self):
        Expense = self.env['hr.expense']
        for project in self:
            total_expenses = 0.0
            if project.analytic_account_id:
                expense_lines = project.analytic_account_id.line_ids.filtered(
                    lambda l: l.amount < 0
                )
                analytic_expenses = abs(sum(expense_lines.mapped('amount')))
                total_expenses += analytic_expenses

            direct_expenses = Expense.search([
                ('project_id', '=', project.id),
                ('state', '=', 'approved'),
            ])
            hr_expenses = sum(direct_expenses.mapped('total_amount') or [])
            total_expenses += hr_expenses

            project.total_expenses = total_expenses

    def action_open_resource_profitability(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Resource Profitability - {self.name}',
            'res_model': 'project.resource.profit',
            'view_mode': 'tree',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'search_default_project_id': self.id,
                'default_project_id': self.id
            },
            'target': 'current'
        }

    def action_refresh_resource_profit(self):
        ResourceProfit = self.env['project.resource.profit']
        for project in self:
            # Remove old rows
            old = ResourceProfit.search([('project_id', '=', project.id)])
            if old:
                old.unlink()
            # Generate new rows
            rows = ResourceProfit._calc_for_project(project)
            if rows:
                ResourceProfit.create(rows)
        return True

    # REPLACE your existing accept_role method with this one
    def accept_role(self, role):
        for rec in self:
            _logger.info(f"✅ accept_role called for {role} on project {rec.name}")

            if role == 'project_manager':
                rec.project_manager_status = 'accepted'
                _logger.info(f"Set project_manager_status to accepted for {rec.name}")
            elif role == 'team_lead':
                rec.team_lead_status = 'accepted'
                _logger.info(f"Set team_lead_status to accepted for {rec.name}")
            elif role == 'department_manager':
                rec.department_manager_status = 'accepted'
                _logger.info(f"Set department_manager_status to accepted for {rec.name}")

            # Send notification to the person who assigned the role
            try:
                rec._send_role_response_notification(role, 'accepted')
                _logger.info(f"Sent response notification for {role} on {rec.name}")
            except Exception as e:
                _logger.error(f"Failed to send response notification: {e}")

            # Send confirmation to the person who accepted
            try:
                rec._send_acceptance_confirmation(role)
                _logger.info(f"Sent acceptance confirmation to {self.env.user.name}")
            except Exception as e:
                _logger.error(f"Failed to send acceptance confirmation: {e}")

            rec.message_post(
                body=f"✅ {self.env.user.name} has accepted the {role.replace('_', ' ').title()} role.",
                message_type="notification"
            )

    # REPLACE your existing decline_role method with this one
    def decline_role(self, role, reason):
        if not reason:
            raise ValidationError("You must provide a reason for declining the role.")

        for rec in self:
            _logger.info(f"❌ decline_role called for {role} on project {rec.name} with reason: {reason}")

            # Send notification to the person who assigned the role
            try:
                rec._send_role_response_notification(role, 'declined')
                _logger.info(f"Sent decline notification for {role} on {rec.name}")
            except Exception as e:
                _logger.error(f"Failed to send decline notification: {e}")

            # Post to chatter
            notification_msg = f"❌ {role.replace('_', ' ').title()} role for {rec.name} has been declined by {self.env.user.name}. Reason: {reason}"
            rec.message_post(
                body=notification_msg,
                message_type="notification"
            )

            # Update status and clear the role
            if role == 'project_manager':
                rec.project_manager_status = 'declined'
                rec.project_manager = False
                _logger.info(f"Cleared project_manager for {rec.name}")
            elif role == 'team_lead':
                rec.team_lead_status = 'declined'
                rec.team_lead_id = False
                _logger.info(f"Cleared team_lead for {rec.name}")
            elif role == 'department_manager':
                rec.department_manager_status = 'declined'
                rec.department_manager_id = False
                _logger.info(f"Cleared department_manager for {rec.name}")

    def _get_pmo(self):
        department = self.env['hr.department'].sudo().browse(5)
        return department.manager_id.id if department and department.manager_id else False

    # ADD THIS NEW METHOD - Send response notification to assigner
    def _send_role_response_notification(self, role, action):
        """Send notification to the person who assigned the role when it's accepted/declined"""
        self.ensure_one()

        _logger.info(f"Sending {action} notification for {role} on project {self.name}")

        # Find who assigned the role (the person who created/wrote the project)
        assigner = self.write_uid or self.create_uid or self.env.user
        assigner = assigner.sudo()

        # Find employee record for assigner
        assigner_employee = self.env['hr.employee'].sudo().search([
            ('user_id', '=', assigner.id)
        ], limit=1)

        if not assigner_employee:
            _logger.warning(f"No employee record found for assigner {assigner.name}")
            # Try fallback to PMO or project manager
            assigner_employee = self.pmo or self.project_manager or self.env.user.employee_id

        if not assigner_employee:
            _logger.error(f"Cannot send response notification: No assigner employee found")
            return False

        if not assigner_employee.work_email:
            _logger.warning(f"Assigner {assigner_employee.name} has no work_email, skipping email")

        role_title = role.replace('_', ' ').title()
        action_text = "accepted" if action == 'accepted' else "declined"
        subject = f"Role {action_text.upper()}: {role_title} for '{self.name}'"

        body_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <h2 style="color: #7C5BBA;">Role Response Notification</h2>
                <p>Hello <strong>{assigner_employee.name}</strong>,</p>
                <p>The <strong>{role_title}</strong> role for project <strong>{self.name}</strong> has been <strong style="color: {'#28a745' if action == 'accepted' else '#dc3545'};">{action_text}</strong> by:</p>
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <strong>Responder:</strong> {self.env.user.name}<br/>
                    <strong>Role:</strong> {role_title}<br/>
                    <strong>Status:</strong> {action_text.upper()}<br/>
                    <strong>Date:</strong> {fields.Datetime.now()}
                </div>
                <p><a href="{self._get_base_url()}/web#id={self.id}&model=project.project&view_type=form" 
                      style="background-color: #7C5BBA; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                    View Project
                </a></p>
            </div>
        """

        # Send email if work email exists
        if assigner_employee.work_email:
            try:
                mail = self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': assigner_employee.work_email,
                    'email_from': self.env.company.email or self.env.user.email,
                })
                mail.send()
                _logger.info(f"Response email sent to {assigner_employee.work_email}")
            except Exception as e:
                _logger.error(f"Failed to send response email: {e}")
        else:
            _logger.warning(f"No work_email for assigner {assigner_employee.name}")

        # Post to chatter
        if assigner_employee.user_id and assigner_employee.user_id.partner_id:
            try:
                self.message_post(
                    body=body_html,
                    subject=subject,
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment',
                    partner_ids=[assigner_employee.user_id.partner_id.id],
                )
                _logger.info(f"Response posted to chatter for {assigner_employee.name}")
            except Exception as e:
                _logger.error(f"Failed to post to chatter: {e}")

        return True

    # ADD THIS NEW METHOD - Send confirmation to person who accepted
    def _send_acceptance_confirmation(self, role):
        self.ensure_one()

        current_user = self.env.user
        current_employee = current_user.employee_id

        _logger.info(f"Sending acceptance confirmation to {current_user.name} for role {role}")

        if not current_employee:
            # Try to get employee from user
            current_employee = self.env['hr.employee'].sudo().search([('user_id', '=', current_user.id)], limit=1)
            if not current_employee:
                _logger.warning(f"No employee record found for {current_user.name}")
                return False

        if not current_employee.work_email:
            _logger.warning(f"Employee {current_employee.name} has no work_email, skipping confirmation email")
            return False

        role_title = role.replace('_', ' ').title()
        subject = f"Confirmation: You accepted the {role_title} role for '{self.name}'"

        body_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <h2 style="color: #28a745;">Role Acceptance Confirmation</h2>
                <p>Hello <strong>{current_user.name}</strong>,</p>
                <p>You have successfully accepted the <strong>{role_title}</strong> role for project:</p>
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <strong>Project:</strong> {self.name}<br/>
                    <strong>Role:</strong> {role_title}<br/>
                    <strong>Date:</strong> {fields.Datetime.now()}
                </div>
                <p>You can now access and manage this project from your dashboard.</p>
                <p><a href="{self._get_base_url()}/web#id={self.id}&model=project.project&view_type=form" 
                      style="background-color: #7C5BBA; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                    Go to Project
                </a></p>
                <hr/>
                <p style="font-size: 12px; color: #666;">If you have any questions, please contact your project coordinator.</p>
            </div>
        """

        try:
            mail = self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body_html,
                'email_to': current_employee.work_email,
                'email_from': self.env.company.email,
            })
            mail.send()
            _logger.info(f"Confirmation email sent to {current_employee.work_email}")
            return True
        except Exception as e:
            _logger.error(f"Failed to send confirmation email: {e}")
            return False

    def _send_role_acceptance_email(self, role):
        for rec in self:
            # 1. Fallback Strategy: Use write_uid, but drop back to env.user if it's a system user or missing
            assigner = rec.write_uid if (rec.write_uid and rec.write_uid.id != 1) else self.env.user
            assigner = assigner.sudo()

            # Find the true assigner employee record
            employee = self.env['hr.employee'].sudo().search(
                [('user_id', '=', assigner.id)],
                limit=1
            )

            # 2. Hard Fallback: If no employee record matches the assigner, target the active project manager or user
            if not employee or not employee.work_email:
                if rec.user_id and rec.user_id.employee_id:
                    employee = rec.user_id.employee_id.sudo()
                else:
                    # Final safety fallback to avoid hitting 'continue' and silencing the system
                    _logger.warning(
                        f"Could not find a valid email assigner for project {rec.name}. Falling back to active session user.")
                    employee = self.env.user.employee_id.sudo()

            if not employee or not employee.work_email:
                _logger.error(f"Notification aborted: No operational email could be resolved for role {role}")
                continue

            subject = f"{role.replace('_', ' ').title()} role for '{rec.name}' has been accepted."

            body = f"""
            <p>Hello,</p>
            <p>
                The <strong>{role.replace('_', ' ').title()}</strong> role
                for project <strong>{rec.name}</strong> has been accepted by <strong>{self.env.user.name}</strong>.
            </p>
            """

            rec.sudo()._notify_user(employee, subject, body)

    def _send_role_decline_email(self, role, reason):
        for project in self:
            assigner = project.write_uid if (project.write_uid and project.write_uid.id != 1) else self.env.user
            assigner = assigner.sudo()

            subject = f"{role.replace('_', ' ').title()} Role Declined"

            body_html = f"""
                <p>Hello,</p>
                <p>The <strong>{role.replace('_', ' ').title()}</strong> role for project <strong>{project.name}</strong> has been declined by <strong>{self.env.user.name}</strong>.</p>
                <p><strong>Reason:</strong> {reason}</p>
            """

            # Post directly to the chatter to maintain an audit trail
            if assigner and assigner.partner_id and assigner.partner_id.email:
                project.sudo().message_post(
                    body=body_html,
                    subject=subject,
                    partner_ids=[assigner.partner_id.id],
                    subtype_xmlid='mail.mt_comment',
                )

            # Also invoke the full notification engine (activities, direct mail execution)
            if assigner.employee_id:
                project.sudo()._notify_user(assigner.employee_id.sudo(), subject, body_html)

    def _notify_user(self, employee, subject, body_html):
        self.ensure_one()
        employee = employee.sudo()

        if not employee.user_id:
            _logger.warning(f"Cannot notify: No user for employee {employee.name}")
            return

        partner = employee.user_id.partner_id
        if not partner:
            _logger.warning(f"Cannot notify: No partner for user {employee.user_id.name}")
            return

        # Subscribe to the project
        if partner.id not in self.message_partner_ids.ids:
            self.sudo().message_subscribe(partner_ids=[partner.id])

        # Post message to chatter
        self.sudo().message_post(
            body=body_html,
            subject=subject,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[partner.id],
        )

        # Create an activity/todo for the user
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)

        if activity_type and employee.user_id:
            self.env['mail.activity'].sudo().create({
                'res_model_id': self.env['ir.model']._get('project.project').id,
                'res_id': self.id,
                'activity_type_id': activity_type.id,
                'summary': subject,
                'note': f"Please review your assignment as {subject.split('Assigned as ')[1] if 'Assigned as' in subject else 'role'}",
                'user_id': employee.user_id.id,
                'date_deadline': fields.Date.today() + timedelta(days=3),
            })

        _logger.info(f"Notification created for {employee.name} regarding {subject}")

    def accept_team_lead(self):
        self.accept_role('team_lead')

    def decline_team_lead(self):
        reason = self.decline_reason or 'No reason provided'
        self.decline_role('team_lead', reason)

    def accept_project_manager(self):
        self.accept_role('project_manager')

    def decline_project_manager(self):
        reason = self.decline_reason or 'No reason provided'
        self.decline_role('project_manager', reason)

    def accept_department_manager(self):
        self.accept_role('department_manager')

    def decline_department_manager(self):
        reason = self.decline_reason or 'No reason provided'
        self.decline_role('department_manager', reason)

    @api.depends('department_id')
    def _compute_department_manager(self):
        for record in self:
            if record.department_id:
                record.department_manager_id = record.department_id.manager_id
                record.team_lead_id = False
            else:
                record.department_manager_id = False
                record.team_lead_id = False

    @api.depends('task_ids.name')
    def _compute_task_names(self):
        for project in self:
            project.task_names = ', '.join(project.task_ids.mapped('name'))

    def _get_base_url(self):
        return self.env['ir.config_parameter'].sudo().get_param('web.base.url').rstrip('/')

    @api.depends('task_ids.timesheet_ids.unit_amount', 'task_ids.timesheet_ids.employee_id', 'expense_ids.total_amount')
    def _compute_budget_utilized(self):
        for project in self:
            total_time_cost = 0.0
            total_expense_cost = 0.0

            for task in project.task_ids:
                for ts in task.timesheet_ids:
                    employee_cost = ts.employee_id.timesheet_cost or 0.0
                    total_time_cost += ts.unit_amount * employee_cost

            for exp in project.expense_ids:
                total_expense_cost += exp.total_amount

            project.budget_utilized = total_time_cost + total_expense_cost

        profitability = fields.Float(
            string="Forecasted Profitability",
            compute='_compute_profitability',
            store=True,
            groups="project.group_project_manager",
            digits=(16, 2)
        )

    # correlation of project financial profitability with employee's profitability score
    @api.depends('task_ids.timesheet_ids')
    def _compute_employee_profitability_score(self):
        for project in self:
            total_score = 0.0
            total_employees = set()

            for task in project.task_ids:
                for ts in task.timesheet_ids:
                    if ts.employee_id:
                        total_score += ts.employee_id.profitability_score or 0.0
                        total_employees.add(ts.employee_id.id)

            project.avg_employee_profitability = total_score / len(total_employees) if total_employees else 0.0

    def _send_role_assignment_email(self, project, role):

        project = project.sudo()

        employee = None
        subject = ''
        assigned_by = (project.write_uid or self.env.user).sudo()

        if role == 'project_manager' and project.project_manager:
            employee = project.project_manager.sudo()
            subject = f"You have been assigned as Project Manager for the project: {project.name}"

        elif role == 'team_lead' and project.team_lead_id:
            employee = project.team_lead_id.sudo()
            subject = f"You have been assigned as Team Lead for the project: {project.name}"

        elif role == 'department_manager' and project.department_manager_id:
            employee = project.department_manager_id.sudo()
            subject = f"You have been assigned as Department Manager for the project: {project.name}"

        if not employee or not employee.user_id or not employee.user_id.partner_id:
            return

        action_url = f"{self._get_base_url()}/web#id={project.id}&model=project.project&view_type=form"

        body_html = (
            f"<p>Dear {employee.name},</p>"
            f"<p>You have been assigned as <b>{role.replace('_', ' ').title()}</b> for the project: <strong>{project.name}</strong>.</p>"
            f"<p>This role has been assigned by {assigned_by.name}.</p>"
            f"<p><a href='{action_url}'>Accept/Decline Role</a></p>"
        )

        if employee.work_email:
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body_html,
                'email_to': employee.work_email,
            }).send()

        partner_id = employee.user_id.partner_id.id

        if partner_id not in project.message_partner_ids.ids:
            project.sudo().message_subscribe(partner_ids=[partner_id])

        project.sudo().message_post(
            body=body_html,
            subject=subject,
            message_type='notification',
            subtype_xmlid="mail.mt_comment",
            partner_ids=[partner_id],
        )

        model = self.env['ir.model'].sudo().search(
            [('model', '=', 'project.project')],
            limit=1
        )

        activity_type = self.env.ref(
            'mail.mail_activity_data_todo',
            raise_if_not_found=False
        )

        if model and activity_type and employee.user_id:
            self.env['mail.activity'].sudo().create({
                'res_model_id': model.id,
                'res_id': project.id,
                'activity_type_id': activity_type.id,
                'summary': subject,
                'note': body_html,
                'user_id': employee.user_id.id,
            })

    # REPLACE your existing _send_role_assignment_notification method with this one
    def _send_role_assignment_notification(self, role_name, employee_record):
        self.ensure_one()
        employee = employee_record.sudo()

        _logger.info(f"🔔 Sending assignment notification for {role_name} to {employee.name}")

        if role_name == 'team_lead' and self.team_lead_status != 'accepted':
            self.team_lead_status = 'pending'
            _logger.info(f"Set team_lead_status to pending for {self.name}")
        elif role_name == 'department_manager' and self.department_manager_status != 'accepted':
            self.department_manager_status = 'pending'
            _logger.info(f"Set department_manager_status to pending for {self.name}")
        elif role_name == 'project_manager' and self.project_manager_status != 'accepted':
            self.project_manager_status = 'pending'
            _logger.info(f"Set project_manager_status to pending for {self.name}")

        if not employee.user_id:
            _logger.warning(f"Cannot send notification to {employee.name}: No user associated")
            return False

        role_title = role_name.replace('_', ' ').title()
        subject = f"Action Required: Assigned as {role_title} for '{self.name}'"

        base_url = self._get_base_url()

        body_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <h2 style="color: #7C5BBA;">Role Assignment Notification</h2>
                <p>Hello <strong>{employee.name}</strong>,</p>
                <p>You have been assigned as the <strong style="color: #7C5BBA;">{role_title}</strong> for the project:</p>
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <strong>Project:</strong> {self.name}<br/>
                    <strong>Assigned by:</strong> {self.env.user.name}<br/>
                    <strong>Date:</strong> {fields.Datetime.now()}
                </div>
                <p>Please review the project requirements and confirm your acceptance or decline of this role.</p>
                <div style="margin: 25px 0;">
                    <a href="{base_url}/web#id={self.id}&model=project.project&view_type=form" 
                       style="background-color: #7C5BBA; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                        📋 Open Project to Respond
                    </a>
                </div>
                <p style="font-size: 12px; color: #666; margin-top: 20px;">
                    <em>Please log into Odoo to accept or decline this role.</em>
                </p>
            </div>
        """

        if employee.work_email:
            try:
                mail = self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': employee.work_email,
                    'email_from': self.env.user.email or self.env.company.email,
                })
                mail.send()
                _logger.info(f"✅ Assignment email sent to {employee.work_email} for role {role_name}")
            except Exception as e:
                _logger.error(f"Failed to send assignment email: {e}")
        else:
            _logger.warning(f"No work_email for {employee.name}, skipping email")

        self._notify_user(employee, subject, body_html)
        return True

    def _send_project_creation_email(self, project):
        pmo = project.pmo
        if not pmo or not pmo.user_id or not pmo.user_id.partner_id:
            return

        user_name = project.create_uid.name or "System"
        project_link = f"{self._get_base_url()}/web#id={project.id}&model=project.project&view_type=form"

        subject = f"New Project Onboarded: {project.name}"

        if project.document_upload_link:
            document_link_section = (
                f"<p><strong>📎 Kindly visit this link to see and upload documents pertaining to this project:</strong></p>"
                f"<p><a href='{project.document_upload_link}' style='background-color: #0078D4; color: white; padding: 10px 20px; "
                f"text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; margin: 10px 0;'>"
                f"📁 Open Microsoft Teams Channel</a></p>"
                f"<p><small>Link: {project.document_upload_link}</small></p>"
            )
        else:
            document_link_section = (
                f"<p style='color: #ff6b6b; padding: 10px; background-color: #fff3cd; border-radius: 5px;'>"
                f"<strong>⚠️ Note:</strong> No Teams channel link has been provided for document sharing. "
                f"Please add a Teams link to the project or contact the sales team.</p>"
            )

        body_html = (
            f"<p>Dear {pmo.name},</p>"
            f"<p>A new project has been onboarded: <strong>{project.name}</strong>.</p>"
            f"<p>The project was created by {user_name} from Sales Order: {project.sale_order_id.name if project.sale_order_id else 'N/A'}. "
            f"This project requires your attention.</p>"
            f"<hr style='margin: 20px 0;'>"
            f"<p>Access the project details here: <a href='{project_link}'>View Project in Odoo</a></p>"
            f"<hr style='margin: 20px 0;'>"
            f"{document_link_section}"
        )

        if pmo.work_email:
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body_html,
                'email_to': pmo.work_email,
            }).send()

        partner_id = pmo.user_id.partner_id.id
        if partner_id not in project.message_partner_ids.ids:
            project.message_subscribe(partner_ids=[partner_id])

        project.message_post(
            body=body_html,
            subject=subject,
            message_type='notification',
            subtype_xmlid="mail.mt_comment",
            partner_ids=[partner_id],
        )

        res_model_id = self.env['ir.model'].sudo().search([('model', '=', 'project.project')], limit=1).id
        activity_type_id = self.env.ref('mail.mail_activity_data_todo').id

        # Create activity with document link if available
        activity_note = f"New project '{project.name}' has been created and requires your attention."
        if project.document_upload_link:
            activity_note += f"\n\nTeams channel for document upload: {project.document_upload_link}"
        else:
            activity_note += f"\n\n⚠️ No Teams channel link provided. Please request the document sharing link from sales."

        self.env['mail.activity'].sudo().create({
            'res_model_id': res_model_id,
            'res_id': project.id,
            'activity_type_id': activity_type_id,
            'summary': f"Review new project: {project.name}",
            'note': activity_note,
            'user_id': pmo.user_id.id,
        })

    @api.depends('budget', 'budget_utilized')
    def _compute_budget_remaining(self):
        for project in self:
            project.budget_remaining = project.budget - project.budget_utilized

    @api.depends('budget_utilized')
    def _compute_forecasted_overrun(self):
        for project in self:
            project.forecasted_budget_overrun = max(project.budget_utilized - project.budget, 0.0)

    def _check_budget_alert(self):
        for project in self:
            if project.budget and project.budget_utilized / project.budget * 100 >= project.budget_alert_threshold and not project.budget_alert_sent:
                self._send_budget_alert(project)

    def _send_budget_alert(self, project):
        pmo = project.pmo
        if not pmo or not pmo.user_id or not pmo.user_id.partner_id:
            return

        subject = f"Budget Alert: {project.name} has exceeded the threshold"
        project_link = f"{self._get_base_url()}/web#id={project.id}&model=project.project&view_type=form"
        body_html = (
            f"<p>Dear {pmo.name},</p>"
            f"<p>The project <strong>{project.name}</strong> has exceeded the configured budget alert threshold of <strong>{project.budget_alert_threshold}%</strong>.</p>"
            f"<p><a href='{project_link}'>View Project</a></p>"
        )

        if pmo.work_email:
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body_html,
                'email_to': pmo.work_email,
            }).send()

        partner_id = pmo.user_id.partner_id.id
        if partner_id not in project.message_partner_ids.ids:
            project.message_subscribe(partner_ids=[partner_id])

        project.message_post(
            body=body_html,
            subject=subject,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[partner_id],
        )

        res_model_id = self.env['ir.model'].sudo().search([('model', '=', 'project.project')], limit=1).id
        activity_type_id = self.env.ref('mail.mail_activity_data_todo').id

        self.env['mail.activity'].sudo().create({
            'res_model_id': res_model_id,
            'res_id': project.id,
            'activity_type_id': activity_type_id,
            'summary': subject,
            'note': body_html,
            'user_id': pmo.user_id.id,
        })

    # this is updated midnight 29th of jan

    document_upload_link = fields.Char(
        string='Document Upload Link (Teams)',
        help="Microsoft Teams channel link for document sharing (copied from Sales Order)",
        copy=False
    )

    @api.depends('sale_order_id', 'sale_order_id.state', 'sale_order_id.amount_total')
    def _compute_budget_from_so(self):
        for project in self:
            new_budget = 0.0

            if project.sale_order_id and project.sale_order_id.state == 'sale':
                new_budget = project.sale_order_id.amount_total  # includes tax
            else:
                # Check for sale orders or lines linked to this project
                related_orders = self.env['sale.order'].search([
                    ('project_id', '=', project.id),
                    ('state', '=', 'sale'),
                ])
                if related_orders:
                    new_budget = sum(related_orders.mapped('amount_total'))
                else:
                    # Fallback: check directly linked sale order lines (rare case)
                    related_order_lines = self.env['sale.order.line'].search([
                        ('project_id', '=', project.id),
                        ('order_id.state', '=', 'sale'),
                    ])
                    if related_order_lines:
                        new_budget = sum(related_order_lines.mapped('price_total'))  # includes tax

            # Update budget only if meaningfully changed
            if abs(project.budget - new_budget) > 0.005:
                project.budget = new_budget

    def _extract_ids(self, val):
        if isinstance(val, models.BaseModel):
            return val.ids
        elif isinstance(val, list):
            ids = []
            for item in val:
                if isinstance(item, tuple) and len(item) == 3 and isinstance(item[2], list):
                    ids.extend(item[2])
                elif isinstance(item, models.BaseModel):
                    ids.append(item.id)
                elif isinstance(item, int):
                    ids.append(item)
            return ids
        elif isinstance(val, int):
            return [val]
        return []

    # NOTE: Keep your existing write method that has the change log functionality
    # But make sure the one above (with notifications) is the one that runs first
    # You may need to merge them. Here's the merged version:

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):

        current_user = self.env.user
        if (current_user.has_group('base.group_system') or
                current_user.has_group('lba_profitability_module.group_project_manager') or
                self.env.context.get('allow_all_projects')):  # Add a context bypass
            return super().search(args, offset=offset, limit=limit, order=order, count=count)

        employee = current_user.employee_id

        if employee:
            role_domain = [
                '|', '|', '|', '|', '|',
                ('pmo', '=', employee.id),
                ('project_manager', '=', employee.id),
                ('department_manager_id', '=', employee.id),
                ('team_lead_id', '=', employee.id),
                ('message_partner_ids', 'in', [current_user.partner_id.id]),
                ('task_ids.assigned_employee_ids', '=', employee.id),
            ]

            full_domain = expression.AND([args, role_domain])

            return super().search(full_domain, offset=offset, limit=limit, order=order, count=count)

        fallback_domain = expression.AND([
            args,
            [('message_partner_ids', 'in', [current_user.partner_id.id])]
        ])

        return super().search(fallback_domain,
                              offset=offset, limit=limit, order=order, count=count)