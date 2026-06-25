# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    assigned_task_count = fields.Integer(
        string='Tasks Assigned',
        compute='_compute_assigned_task_count'
    )

    can_reassign_tasks = fields.Boolean(
        string='Can Reassign Tasks',
        compute='_compute_can_reassign_tasks'
    )

    @api.depends('user_id')
    def _compute_assigned_task_count(self):
        for employee in self:
            employee.assigned_task_count = self.env['project.task'].search_count([
                ('assigned_employee_ids', 'in', employee.id),
                ('stage_id.is_closed', '=', False)
            ])

    @api.depends('user_id')
    def _compute_can_reassign_tasks(self):
        for employee in self:
            user = employee.user_id
            can_reassign = False

            if user:
                # Using parent module groups
                if user.has_group('lba_profitability_module.group_pmo'):
                    can_reassign = True
                elif user.has_group('lba_profitability_module.group_project_manager'):
                    can_reassign = True
                elif user.has_group('lba_profitability_module.group_department_manager'):
                    can_reassign = True
                elif user.has_group('lba_profitability_module.group_team_lead'):
                    can_reassign = True

            employee.can_reassign_tasks = can_reassign

    def action_reassign_employee_tasks(self):
        if not self.assigned_task_count:
            raise ValidationError(_('This employee has no assigned tasks.'))

        user = self.env.user
        # Using parent module groups
        if not (user.has_group('lba_profitability_module.group_pmo') or
                user.has_group('lba_profitability_module.group_project_manager') or
                user.has_group('lba_profitability_module.group_department_manager') or
                user.has_group('lba_profitability_module.group_team_lead')):
            raise AccessError(_('Only PMO, PM, Dept Mgr, and Team Lead can reassign tasks.'))

        first_task = self.env['project.task'].search([
            ('assigned_employee_ids', 'in', self.id),
            ('stage_id.is_closed', '=', False)
        ], limit=1)

        if not first_task:
            raise ValidationError(_('No active tasks found for this employee.'))

        return {
            'name': _('Reassign Employee Tasks'),
            'type': 'ir.actions.act_window',
            'res_model': 'task.reassignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_task_id': first_task.id,
                'default_current_employee_id': self.id,
                'default_reassign_all_employee_tasks': True,
            }
        }