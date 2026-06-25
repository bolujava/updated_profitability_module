# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class TaskReassignmentHistory(models.Model):
    _name = 'task.reassignment.history'
    _description = 'Task Reassignment History'
    _order = 'create_date DESC'
    _rec_name = 'display_name'

    # CRITICAL: This field is required for the One2many in project.task
    task_id = fields.Many2one(
        'project.task',
        string='Task',
        required=True,
        ondelete='cascade',
        index=True
    )

    task_name = fields.Char(
        related='task_id.name',
        string='Task Name',
        store=True
    )

    from_employee_id = fields.Many2one(
        'hr.employee',
        string='Previous Employee',
        required=True
    )
    from_employee_name = fields.Char(
        related='from_employee_id.name',
        string='Previous Employee Name'
    )

    to_employee_id = fields.Many2one(
        'hr.employee',
        string='New Employee',
        required=True
    )
    to_employee_name = fields.Char(
        related='to_employee_id.name',
        string='New Employee Name'
    )

    reassigned_by_id = fields.Many2one(
        'res.users',
        string='Reassigned By',
        default=lambda self: self.env.user
    )
    reassigned_by_name = fields.Char(
        related='reassigned_by_id.name',
        string='Reassigned By Name'
    )

    # ===== THIS FIELD IS REQUIRED FOR THE VIEW =====
    reassigned_by_role = fields.Selection([
        ('pmo', 'PMO'),
        ('pm', 'Project Manager'),
        ('dept_mgr', 'Department Manager'),
        ('team_lead', 'Team Lead'),
        ('user', 'User'),
    ], string='Reassigned By Role', compute='_compute_reassigned_by_role', store=True)

    reassigned_date = fields.Datetime(
        string='Reassigned Date',
        default=fields.Datetime.now
    )

    transfer_time = fields.Boolean(
        string='Time Transferred',
        default=False
    )

    timesheets_transferred = fields.Integer(
        string='Timesheets Transferred',
        default=0
    )

    hours_transferred = fields.Float(
        string='Hours Transferred',
        default=0.0
    )

    notes = fields.Text(string='Notes')

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    @api.depends('task_id.name', 'from_employee_id.name', 'to_employee_id.name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = _('Reassignment: %s (%s → %s)') % (
                record.task_id.name or 'Task',
                record.from_employee_id.name or 'Unknown',
                record.to_employee_id.name or 'Unknown'
            )

    # ===== THIS COMPUTE METHOD IS REQUIRED FOR THE FIELD =====
    @api.depends('reassigned_by_id')
    def _compute_reassigned_by_role(self):
        for record in self:
            user = record.reassigned_by_id
            if not user:
                record.reassigned_by_role = False
            elif user.has_group('lba_profitability_module.group_pmo'):
                record.reassigned_by_role = 'pmo'
            elif user.has_group('lba_profitability_module.group_project_manager'):
                record.reassigned_by_role = 'pm'
            elif user.has_group('lba_profitability_module.group_department_manager'):
                record.reassigned_by_role = 'dept_mgr'
            elif user.has_group('lba_profitability_module.group_team_lead'):
                record.reassigned_by_role = 'team_lead'
            else:
                record.reassigned_by_role = 'user'

    @api.model
    def create(self, vals):
        record = super(TaskReassignmentHistory, self).create(vals)
        if record.task_id:
            record.task_id.reassigned_count = len(record.task_id.reassignment_history_ids)
            record.task_id.last_reassignment_date = record.reassigned_date
        return record