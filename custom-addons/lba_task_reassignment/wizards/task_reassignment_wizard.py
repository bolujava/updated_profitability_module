# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
import logging

_logger = logging.getLogger(__name__)


class TaskReassignmentWizard(models.TransientModel):
    _name = 'task.reassignment.wizard'
    _description = 'Task Reassignment Wizard'

    # ===== BASIC FIELDS =====
    task_id = fields.Many2one('project.task', string='Task', required=True)
    project_id = fields.Many2one('project.project', string='Project', related='task_id.project_id', readonly=True)
    current_employee_id = fields.Many2one('hr.employee', string='Current Employee', readonly=True)
    new_employee_id = fields.Many2one('hr.employee', string='New Employee', required=True)

    # ===== OPTIONS =====
    transfer_time = fields.Boolean(
        string='Transfer Logged Time',
        default=False,
        help='Transfer all timesheet entries from current to new employee'
    )

    reassign_all_employee_tasks = fields.Boolean(
        string='Reassign All Tasks Across All Projects',
        default=False,
        help='Reassign all tasks from this employee'
    )

    reassign_similar_tasks = fields.Boolean(
        string='Reassign Similar Tasks',
        default=False,
        help='Reassign all tasks in the same project and stage'
    )

    # ===== COMPUTED FIELDS =====
    similar_tasks_count = fields.Integer(
        string='Similar Tasks Count',
        compute='_compute_similar_tasks_count'
    )

    employee_tasks_count = fields.Integer(
        string='Employee Tasks Count',
        compute='_compute_employee_tasks_count'
    )

    hours_to_transfer = fields.Float(
        string='Hours to Transfer',
        compute='_compute_hours_to_transfer'
    )

    timesheets_to_transfer = fields.Integer(
        string='Timesheets to Transfer',
        compute='_compute_hours_to_transfer'
    )

    # ===== COMPUTE METHODS =====
    @api.depends('task_id', 'reassign_similar_tasks')
    def _compute_similar_tasks_count(self):
        for wizard in self:
            if wizard.reassign_similar_tasks and wizard.task_id:
                similar_tasks = wizard.env['project.task'].search([
                    ('project_id', '=', wizard.task_id.project_id.id),
                    ('stage_id', '=', wizard.task_id.stage_id.id),
                    ('id', '!=', wizard.task_id.id),
                    ('assigned_employee_ids', '!=', False)
                ])
                wizard.similar_tasks_count = len(similar_tasks)
            else:
                wizard.similar_tasks_count = 0

    @api.depends('current_employee_id')
    def _compute_employee_tasks_count(self):
        for wizard in self:
            if wizard.current_employee_id:
                tasks = wizard.env['project.task'].search([
                    ('assigned_employee_ids', 'in', wizard.current_employee_id.id),
                    ('stage_id.is_closed', '=', False)
                ])
                wizard.employee_tasks_count = len(tasks)
            else:
                wizard.employee_tasks_count = 0

    @api.depends('task_id', 'current_employee_id')
    def _compute_hours_to_transfer(self):
        for wizard in self:
            if wizard.task_id and wizard.current_employee_id:
                timesheets = wizard.task_id.timesheet_ids.filtered(
                    lambda ts: ts.employee_id.id == wizard.current_employee_id.id
                )
                wizard.timesheets_to_transfer = len(timesheets)
                wizard.hours_to_transfer = sum(timesheets.mapped('unit_amount'))
            else:
                wizard.timesheets_to_transfer = 0
                wizard.hours_to_transfer = 0.0

    # ===== ONCHANGE METHODS =====
    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.task_id:
            # Check permission
            if not self.task_id.can_reassign:
                return {
                    'warning': {
                        'title': _('Permission Denied'),
                        'message': _('You do not have permission to reassign this task.'),
                    }
                }

            self.current_employee_id = self.task_id.assigned_employee_ids[
                0] if self.task_id.assigned_employee_ids else False

            # Set domain for new employee to exclude current
            if self.current_employee_id:
                return {
                    'domain': {
                        'new_employee_id': [('id', '!=', self.current_employee_id.id)]
                    }
                }
        return {}

    @api.onchange('new_employee_id')
    def _onchange_new_employee(self):
        if self.new_employee_id and self.current_employee_id:
            if self.new_employee_id == self.current_employee_id:
                return {
                    'warning': {
                        'title': _('Invalid Selection'),
                        'message': _('Cannot reassign to the same employee. Please select a different employee.'),
                    }
                }

    @api.onchange('reassign_all_employee_tasks')
    def _onchange_reassign_all_employee_tasks(self):
        if self.reassign_all_employee_tasks:
            return {
                'warning': {
                    'title': _('Warning'),
                    'message': _('This will reassign ALL tasks from %s. This action cannot be undone.') % (
                        self.current_employee_id.name if self.current_employee_id else 'this employee'
                    ),
                }
            }

    # ===== MAIN ACTION METHOD =====
    def action_reassign(self):
        """Execute the reassignment"""
        if not self.new_employee_id:
            raise ValidationError(_('Please select a new employee.'))

        if not self.task_id:
            raise ValidationError(_('No task selected.'))

        if not self.task_id.can_reassign:
            raise AccessError(_('You do not have permission to reassign this task.'))

        if self.new_employee_id == self.current_employee_id:
            raise ValidationError(_('Cannot reassign to the same employee.'))

        tasks_to_reassign = self.task_id

        # Get similar tasks if requested
        if self.reassign_similar_tasks:
            similar_tasks = self.env['project.task'].search([
                ('project_id', '=', self.task_id.project_id.id),
                ('stage_id', '=', self.task_id.stage_id.id),
                ('id', '!=', self.task_id.id),
                ('assigned_employee_ids', '=', self.current_employee_id.id)
            ])
            tasks_to_reassign |= similar_tasks

        # Get all employee tasks if requested
        if self.reassign_all_employee_tasks and self.current_employee_id:
            all_tasks = self.env['project.task'].search([
                ('assigned_employee_ids', 'in', self.current_employee_id.id),
                ('stage_id.is_closed', '=', False)
            ])
            tasks_to_reassign |= all_tasks

        if not tasks_to_reassign:
            raise ValidationError(_('No tasks found to reassign.'))

        # Execute reassignment
        reassigned_count = tasks_to_reassign.bulk_reassign_employee(
            self.current_employee_id.id,
            self.new_employee_id.id,
            self.transfer_time
        )

        if reassigned_count == 0:
            raise UserError(_('No tasks were reassigned.'))

        # Show success message
        message = _('Successfully reassigned %d task(s) from %s to %s.') % (
            reassigned_count,
            self.current_employee_id.name,
            self.new_employee_id.name
        )

        if self.transfer_time:
            message += _(' Timesheets were transferred.')

        # Return to history view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'task.reassignment.history',
            'view_mode': 'tree,form',
            'target': 'current',
            'domain': [('task_id', 'in', tasks_to_reassign.ids)],
            'name': _('Reassignment History'),
            'context': {'create': False},
        }

    def action_cancel(self):
        """Cancel the reassignment"""
        return {'type': 'ir.actions.act_window_close'}