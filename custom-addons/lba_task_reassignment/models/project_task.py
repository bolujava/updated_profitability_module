# # -*- coding: utf-8 -*-
# from odoo import models, fields, api, _
# from odoo.exceptions import ValidationError, UserError, AccessError
# import logging
#
# _logger = logging.getLogger(__name__)
#
#
# class ProjectTask(models.Model):
#     _inherit = 'project.task'
#
#     # ===== REASSIGNMENT FIELDS =====
#     reassignment_history_ids = fields.One2many(
#         'task.reassignment.history',
#         'task_id',
#         string='Reassignment History'
#     )
#
#     reassigned_count = fields.Integer(
#         string='Times Reassigned',
#         compute='_compute_reassigned_count',
#         store=True
#     )
#
#     last_reassignment_date = fields.Datetime(
#         string='Last Reassignment Date',
#         compute='_compute_last_reassignment',
#         store=True
#     )
#
#     can_reassign = fields.Boolean(
#         string='Can Reassign',
#         compute='_compute_can_reassign'
#     )
#
#     # ===== COMPUTE METHODS =====
#     @api.depends('reassignment_history_ids')
#     def _compute_reassigned_count(self):
#         for task in self:
#             task.reassigned_count = len(task.reassignment_history_ids)
#
#     @api.depends('reassignment_history_ids.reassigned_date')
#     def _compute_last_reassignment(self):
#         for task in self:
#             last_history = task.reassignment_history_ids.sorted('reassigned_date', reverse=True)[:1]
#             task.last_reassignment_date = last_history.reassigned_date if last_history else False
#
#     @api.depends('assigned_employee_ids')
#     def _compute_can_reassign(self):
#         """Check if current user can reassign this task based on their role"""
#         for task in self:
#             user = self.env.user
#             can_reassign = False
#
#             # Check PMO - using parent module group
#             if user.has_group('lba_profitability_module.group_pmo'):
#                 can_reassign = True
#
#             # Check PM (Project Manager) - using parent module group
#             elif user.has_group('lba_profitability_module.group_project_manager'):
#                 if task.project_id and task.project_id.project_manager.id == user.employee_id.id:
#                     can_reassign = True
#
#             # Check Department Manager - using parent module group
#             elif user.has_group('lba_profitability_module.group_department_manager'):
#                 if task.project_id and task.project_id.department_manager_id.id == user.employee_id.id:
#                     can_reassign = True
#
#             # Check Team Lead - using parent module group
#             elif user.has_group('lba_profitability_module.group_team_lead'):
#                 if task.project_id and task.project_id.team_lead_id.id == user.employee_id.id:
#                     can_reassign = True
#
#             task.can_reassign = can_reassign
#
#
#     def action_reassign_task(self):
#         """Open reassignment wizard"""
#         if not self.can_reassign:
#             raise AccessError(_(
#                 'Only PMO, Project Managers, Department Managers, and Team Leads can reassign tasks.'
#             ))
#
#         if not self.assigned_employee_ids:
#             raise ValidationError(_('This task has no employee assigned.'))
#
#         return {
#             'name': _('Reassign Task'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'task.reassignment.wizard',
#             'view_mode': 'form',
#             'target': 'new',
#             'context': {
#                 'default_task_id': self.id,
#                 'default_current_employee_id': self.assigned_employee_ids[
#                     0].id if self.assigned_employee_ids else False,
#             }
#         }
#
#     # ===== REASSIGNMENT LOGIC =====
#     def reassign_employee(self, from_employee, to_employee, transfer_time=False):
#         """Reassign a task from one employee to another"""
#         self.ensure_one()
#
#         if not from_employee or not to_employee:
#             raise ValidationError(_('Both employees must be specified.'))
#
#         if from_employee == to_employee:
#             raise ValidationError(_('Cannot reassign to the same employee.'))
#
#         if not self.can_reassign:
#             raise AccessError(_('You do not have permission to reassign this task.'))
#
#         timesheets_to_transfer = self.timesheet_ids.filtered(
#             lambda ts: ts.employee_id.id == from_employee.id
#         )
#         hours_to_transfer = sum(timesheets_to_transfer.mapped('unit_amount'))
#
#         # Update task assignment - Remove old employee, add new one
#         self.write({
#             'assigned_employee_ids': [(6, 0, [to_employee.id])]
#         })
#
#         if transfer_time and timesheets_to_transfer:
#             timesheets_to_transfer.write({
#                 'employee_id': to_employee.id,
#                 'user_id': to_employee.user_id.id if to_employee.user_id else False,
#             })
#
#             _logger.info(
#                 f"Transferred {len(timesheets_to_transfer)} timesheets "
#                 f"({hours_to_transfer} hours) from {from_employee.name} to {to_employee.name}"
#             )
#
#             # Update parent module fields
#             self.invalidate_cache(['total_timesheet_hours', 'average_timesheet_hours'])
#             if hasattr(self, '_compute_timesheet_totals'):
#                 self._compute_timesheet_totals()
#             if self.project_id and hasattr(self.project_id, '_compute_profitability'):
#                 self.project_id._compute_profitability()
#             if self.sale_line_id and hasattr(self.sale_line_id, '_compute_delivered_from_tasks'):
#                 self.sale_line_id._compute_delivered_from_tasks()
#
#         # Create history record
#         self.env['task.reassignment.history'].create({
#             'task_id': self.id,
#             'from_employee_id': from_employee.id,
#             'to_employee_id': to_employee.id,
#             'reassigned_by_id': self.env.user.id,
#             'transfer_time': transfer_time,
#             'timesheets_transferred': len(timesheets_to_transfer) if transfer_time else 0,
#             'hours_transferred': hours_to_transfer if transfer_time else 0.0,
#         })
#
#         self._notify_reassignment(from_employee, to_employee)
#         return True
#
#     def bulk_reassign_employee(self, from_employee_id, to_employee_id, transfer_time=False):
#         """Bulk reassign multiple tasks"""
#         if not self:
#             return 0
#
#         from_employee = self.env['hr.employee'].browse(from_employee_id)
#         to_employee = self.env['hr.employee'].browse(to_employee_id)
#
#         if not from_employee or not to_employee:
#             raise ValidationError(_('Invalid employees selected.'))
#
#         reassigned_count = 0
#         task_ids = []
#         total_hours_transferred = 0.0
#         total_timesheets_transferred = 0
#
#         for task in self:
#             try:
#                 timesheets = task.timesheet_ids.filtered(
#                     lambda ts: ts.employee_id.id == from_employee.id
#                 )
#                 hours = sum(timesheets.mapped('unit_amount'))
#
#                 task.reassign_employee(from_employee, to_employee, transfer_time)
#                 reassigned_count += 1
#                 task_ids.append(task.id)
#
#                 if transfer_time:
#                     total_hours_transferred += hours
#                     total_timesheets_transferred += len(timesheets)
#
#             except Exception as e:
#                 _logger.error(f"Failed to reassign task {task.id}: {str(e)}")
#
#         if task_ids:
#             tasks = self.browse(task_ids)
#             if hasattr(tasks, '_compute_timesheet_totals'):
#                 tasks._compute_timesheet_totals()
#             projects = tasks.mapped('project_id')
#             if projects and hasattr(projects, '_compute_profitability'):
#                 projects._compute_profitability()
#             sale_lines = tasks.mapped('sale_line_id')
#             if sale_lines and hasattr(sale_lines, '_compute_delivered_from_tasks'):
#                 sale_lines._compute_delivered_from_tasks()
#
#         _logger.info(
#             f"Bulk reassignment complete: {reassigned_count} tasks reassigned. "
#             f"Transferred {total_timesheets_transferred} timesheets "
#             f"({total_hours_transferred} hours)"
#         )
#
#         return reassigned_count
#
#     def _notify_reassignment(self, from_employee, to_employee):
#         """Send notifications about reassignment"""
#         try:
#             base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
#             if not base_url:
#                 base_url = 'http://localhost:8069'
#
#             if from_employee.work_email:
#                 self.env['mail.mail'].sudo().create({
#                     'subject': _('Task Reassigned: %s') % self.name,
#                     'body_html': f"""
#                         <p>Hello {from_employee.name},</p>
#                         <p>Task <strong>{self.name}</strong> has been reassigned to {to_employee.name}.</p>
#                         <p>Project: {self.project_id.name if self.project_id else 'N/A'}</p>
#                         <p>Deadline: {self.date_deadline or 'No Deadline'}</p>
#                         <a href="{base_url}/web#id={self.id}&model=project.task&view_type=form">
#                             View Task Details
#                         </a>
#                     """,
#                     'email_to': from_employee.work_email,
#                 }).send()
#
#             if to_employee.work_email:
#                 self.env['mail.mail'].sudo().create({
#                     'subject': _('Task Assigned: %s') % self.name,
#                     'body_html': f"""
#                         <p>Hello {to_employee.name},</p>
#                         <p>You have been assigned to task <strong>{self.name}</strong>.</p>
#                         <p>Project: {self.project_id.name if self.project_id else 'N/A'}</p>
#                         <p>Deadline: {self.date_deadline or 'No Deadline'}</p>
#                         <p>This task was previously assigned to {from_employee.name}.</p>
#                         <a href="{base_url}/web#id={self.id}&model=project.task&view_type=form">
#                             View Task Details
#                         </a>
#                     """,
#                     'email_to': to_employee.work_email,
#                 }).send()
#
#         except Exception as e:
#             _logger.error(f"Failed to send reassignment notification: {str(e)}")
#
#     def action_open_reassignment_history(self):
#         """Open reassignment history for this task"""
#         self.ensure_one()
#
#         if not self.can_reassign:
#             raise AccessError(_(
#                 'Only PMO, Project Managers, Department Managers, and Team Leads can view reassignment history.'
#             ))
#
#         # Get history records using sudo
#         history_records = self.env['task.reassignment.history'].sudo().search([
#             ('task_id', '=', self.id)
#         ])
#
#         if not history_records:
#             return {
#                 'type': 'ir.actions.client',
#                 'tag': 'display_notification',
#                 'params': {
#                     'title': _('No Reassignment History'),
#                     'message': _('This task has no reassignment history.'),
#                     'type': 'info',
#                     'sticky': False,
#                 }
#             }
#
#         return {
#             'type': 'ir.actions.act_window',
#             'res_model': 'task.reassignment.history',
#             'view_mode': 'tree,form',
#             'target': 'current',
#             'domain': [('id', 'in', history_records.ids)],
#             'name': _('Reassignment History'),
#             'context': {
#                 'create': False,
#                 'edit': False,
#                 'delete': False,
#             }
#         }


# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
import logging

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # ===== REASSIGNMENT FIELDS =====
    reassignment_history_ids = fields.One2many(
        'task.reassignment.history',
        'task_id',
        string='Reassignment History'
    )

    reassigned_count = fields.Integer(
        string='Times Reassigned',
        compute='_compute_reassigned_count',
        store=True
    )

    last_reassignment_date = fields.Datetime(
        string='Last Reassignment Date',
        compute='_compute_last_reassignment',
        store=True
    )

    can_reassign = fields.Boolean(
        string='Can Reassign',
        compute='_compute_can_reassign'
    )

    # ===== COMPUTE METHODS =====
    @api.depends('reassignment_history_ids')
    def _compute_reassigned_count(self):
        for task in self:
            task.reassigned_count = len(task.reassignment_history_ids)

    @api.depends('reassignment_history_ids.reassigned_date')
    def _compute_last_reassignment(self):
        for task in self:
            last_history = task.reassignment_history_ids.sorted('reassigned_date', reverse=True)[:1]
            task.last_reassignment_date = last_history.reassigned_date if last_history else False

    @api.depends('assigned_employee_ids')
    def _compute_can_reassign(self):
        """Check if current user can reassign this task based on their role"""
        for task in self:
            user = self.env.user
            can_reassign = False

            # Check PMO - using parent module group
            if user.has_group('lba_profitability_module.group_pmo'):
                can_reassign = True

            # Check PM (Project Manager) - using parent module group
            elif user.has_group('lba_profitability_module.group_project_manager'):
                if task.project_id and task.project_id.project_manager.id == user.employee_id.id:
                    can_reassign = True

            # Check Department Manager - using parent module group
            elif user.has_group('lba_profitability_module.group_department_manager'):
                if task.project_id and task.project_id.department_manager_id.id == user.employee_id.id:
                    can_reassign = True

            # Check Team Lead - using parent module group
            elif user.has_group('lba_profitability_module.group_team_lead'):
                if task.project_id and task.project_id.team_lead_id.id == user.employee_id.id:
                    can_reassign = True

            task.can_reassign = can_reassign

    @api.onchange('assigned_employee_ids')
    def _onchange_assigned_employee_ids(self):
        if self.env.context.get('import_file') or self.env.context.get('load_data'):
            return

        if not self._origin:
            return

        if self.env.context.get('skip_reassignment_check'):
            return

        original_employees = self._origin.assigned_employee_ids

        if original_employees:
            # Check if any employees were removed
            removed = set(original_employees.ids) - set(self.assigned_employee_ids.ids)
            if removed:
                # Revert the change
                self.assigned_employee_ids = [(6, 0, original_employees.ids)]
                raise UserError(
                    _("☕ Try using the 'Reassign Employee' button to reassign this employee instead of removing them directly.")
                )

    def write(self, vals):

        if 'assigned_employee_ids' in vals:
            if not self.env.context.get('import_file') and not self.env.context.get('load_data'):
                if not self.env.context.get('skip_reassignment_check'):
                    for task in self:
                        if not task._origin:
                            continue

                        current_employees = task._origin.assigned_employee_ids

                        # If there are current employees
                        if current_employees and vals['assigned_employee_ids']:
                            if isinstance(vals['assigned_employee_ids'], list) and len(
                                    vals['assigned_employee_ids']) > 0:
                                cmd = vals['assigned_employee_ids'][0]

                                # Command (5) = Remove all
                                if cmd[0] == 5:
                                    raise UserError(
                                        _("☕ Try using the 'Reassign Employee' button to reassign this employee instead of removing them directly.")
                                    )

                                # Command (3) = Remove specific employee
                                elif cmd[0] == 3:
                                    if len(current_employees) == 1:
                                        raise UserError(
                                            _("☕ Try using the 'Reassign Employee' button to reassign this employee instead of removing them directly.")
                                        )

                                # Command (6) = Full replace
                                elif cmd[0] == 6:
                                    new_ids = cmd[2] if len(cmd) > 2 else []

                                    # If we're removing all employees (empty list)
                                    if len(new_ids) == 0:
                                        raise UserError(
                                            _("☕ Try using the 'Reassign Employee' button to reassign this employee instead of removing them directly.")
                                        )

                                    # If we're replacing with different employees
                                    elif len(new_ids) != len(current_employees):
                                        old_ids = set(current_employees.ids)
                                        new_ids_set = set(new_ids)
                                        removed = old_ids - new_ids_set
                                        if removed:
                                            raise UserError(
                                                _("☕ Try using the 'Reassign Employee' button to reassign this employee instead of removing them directly.")
                                            )

        return super(ProjectTask, self).write(vals)

    def action_reassign_task(self):
        """Open reassignment wizard"""
        if not self.can_reassign:
            raise AccessError(_(
                'Only PMO, Project Managers, Department Managers, and Team Leads can reassign tasks.'
            ))

        if not self.assigned_employee_ids:
            raise ValidationError(_('This task has no employee assigned.'))

        return {
            'name': _('Reassign Task'),
            'type': 'ir.actions.act_window',
            'res_model': 'task.reassignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_task_id': self.id,
                'default_current_employee_id': self.assigned_employee_ids[
                    0].id if self.assigned_employee_ids else False,
            }
        }

    # ===== REASSIGNMENT LOGIC =====
    def reassign_employee(self, from_employee, to_employee, transfer_time=False):
        """Reassign a task from one employee to another"""
        self.ensure_one()

        if not from_employee or not to_employee:
            raise ValidationError(_('Both employees must be specified.'))

        if from_employee == to_employee:
            raise ValidationError(_('Cannot reassign to the same employee.'))

        if not self.can_reassign:
            raise AccessError(_('You do not have permission to reassign this task.'))

        timesheets_to_transfer = self.timesheet_ids.filtered(
            lambda ts: ts.employee_id.id == from_employee.id
        )
        hours_to_transfer = sum(timesheets_to_transfer.mapped('unit_amount'))
        self.with_context(skip_reassignment_check=True).write({
            'assigned_employee_ids': [(6, 0, [to_employee.id])]
        })

        if transfer_time and timesheets_to_transfer:
            timesheets_to_transfer.write({
                'employee_id': to_employee.id,
                'user_id': to_employee.user_id.id if to_employee.user_id else False,
            })

            _logger.info(
                f"Transferred {len(timesheets_to_transfer)} timesheets "
                f"({hours_to_transfer} hours) from {from_employee.name} to {to_employee.name}"
            )

            self.invalidate_cache(['total_timesheet_hours', 'average_timesheet_hours'])
            if hasattr(self, '_compute_timesheet_totals'):
                self._compute_timesheet_totals()
            if self.project_id and hasattr(self.project_id, '_compute_profitability'):
                self.project_id._compute_profitability()
            if self.sale_line_id and hasattr(self.sale_line_id, '_compute_delivered_from_tasks'):
                self.sale_line_id._compute_delivered_from_tasks()

        self.env['task.reassignment.history'].create({
            'task_id': self.id,
            'from_employee_id': from_employee.id,
            'to_employee_id': to_employee.id,
            'reassigned_by_id': self.env.user.id,
            'transfer_time': transfer_time,
            'timesheets_transferred': len(timesheets_to_transfer) if transfer_time else 0,
            'hours_transferred': hours_to_transfer if transfer_time else 0.0,
        })

        self._notify_reassignment(from_employee, to_employee)
        return True

    def bulk_reassign_employee(self, from_employee_id, to_employee_id, transfer_time=False):
        """Bulk reassign multiple tasks"""
        if not self:
            return 0

        from_employee = self.env['hr.employee'].browse(from_employee_id)
        to_employee = self.env['hr.employee'].browse(to_employee_id)

        if not from_employee or not to_employee:
            raise ValidationError(_('Invalid employees selected.'))

        reassigned_count = 0
        task_ids = []
        total_hours_transferred = 0.0
        total_timesheets_transferred = 0

        for task in self:
            try:
                timesheets = task.timesheet_ids.filtered(
                    lambda ts: ts.employee_id.id == from_employee.id
                )
                hours = sum(timesheets.mapped('unit_amount'))

                task.reassign_employee(from_employee, to_employee, transfer_time)
                reassigned_count += 1
                task_ids.append(task.id)

                if transfer_time:
                    total_hours_transferred += hours
                    total_timesheets_transferred += len(timesheets)

            except Exception as e:
                _logger.error(f"Failed to reassign task {task.id}: {str(e)}")

        if task_ids:
            tasks = self.browse(task_ids)
            if hasattr(tasks, '_compute_timesheet_totals'):
                tasks._compute_timesheet_totals()
            projects = tasks.mapped('project_id')
            if projects and hasattr(projects, '_compute_profitability'):
                projects._compute_profitability()
            sale_lines = tasks.mapped('sale_line_id')
            if sale_lines and hasattr(sale_lines, '_compute_delivered_from_tasks'):
                sale_lines._compute_delivered_from_tasks()

        _logger.info(
            f"Bulk reassignment complete: {reassigned_count} tasks reassigned. "
            f"Transferred {total_timesheets_transferred} timesheets "
            f"({total_hours_transferred} hours)"
        )

        return reassigned_count

    def _notify_reassignment(self, from_employee, to_employee):
        """Send notifications about reassignment"""
        try:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            if not base_url:
                base_url = 'http://localhost:8069'

            if from_employee.work_email:
                self.env['mail.mail'].sudo().create({
                    'subject': _('Task Reassigned: %s') % self.name,
                    'body_html': f"""
                        <p>Hello {from_employee.name},</p>
                        <p>Task <strong>{self.name}</strong> has been reassigned to {to_employee.name}.</p>
                        <p>Project: {self.project_id.name if self.project_id else 'N/A'}</p>
                        <p>Deadline: {self.date_deadline or 'No Deadline'}</p>
                        <a href="{base_url}/web#id={self.id}&model=project.task&view_type=form">
                            View Task Details
                        </a>
                    """,
                    'email_to': from_employee.work_email,
                }).send()

            if to_employee.work_email:
                self.env['mail.mail'].sudo().create({
                    'subject': _('Task Assigned: %s') % self.name,
                    'body_html': f"""
                        <p>Hello {to_employee.name},</p>
                        <p>You have been assigned to task <strong>{self.name}</strong>.</p>
                        <p>Project: {self.project_id.name if self.project_id else 'N/A'}</p>
                        <p>Deadline: {self.date_deadline or 'No Deadline'}</p>
                        <p>This task was previously assigned to {from_employee.name}.</p>
                        <a href="{base_url}/web#id={self.id}&model=project.task&view_type=form">
                            View Task Details
                        </a>
                    """,
                    'email_to': to_employee.work_email,
                }).send()

        except Exception as e:
            _logger.error(f"Failed to send reassignment notification: {str(e)}")

    def action_open_reassignment_history(self):
        """Open reassignment history for this task"""
        self.ensure_one()

        if not self.can_reassign:
            raise AccessError(_(
                'Only PMO, Project Managers, Department Managers, and Team Leads can view reassignment history.'
            ))

        # Get history records using sudo
        history_records = self.env['task.reassignment.history'].sudo().search([
            ('task_id', '=', self.id)
        ])

        if not history_records:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Reassignment History'),
                    'message': _('This task has no reassignment history.'),
                    'type': 'info',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'task.reassignment.history',
            'view_mode': 'tree,form',
            'target': 'current',
            'domain': [('id', 'in', history_records.ids)],
            'name': _('Reassignment History'),
            'context': {
                'create': False,
                'edit': False,
                'delete': False,
            }
        }