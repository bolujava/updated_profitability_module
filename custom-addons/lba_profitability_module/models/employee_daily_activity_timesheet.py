# from odoo import models, fields, api
# from odoo.exceptions import ValidationError
#
#
# # =====================================================
# # DAILY ACTIVITY TIMESHEET EXTENSION
# # =====================================================
# class EmployeeDailyActivityTimesheet(models.Model):
#     _inherit = 'employee.daily.activity'
#
#     project_id = fields.Many2one(
#         'project.project',
#         string="Project",
#         required=True,
#         tracking=True
#     )
#
#     task_id = fields.Many2one(
#         'project.task',
#         string="Task",
#         domain="[('project_id', '=', project_id)]",
#         tracking=True
#     )
#
#     sale_line_id = fields.Many2one(
#         'sale.order.line',
#         string="Sales Order Line",
#         related='task_id.sale_line_id',
#         store=True,
#         readonly=True
#     )
#
#     timesheet_id = fields.Many2one(
#         'account.analytic.line',
#         string="Timesheet",
#         readonly=True,
#         copy=False
#     )
#
#     @api.constrains('task_id', 'project_id')
#     def _check_task_project_match(self):
#         for rec in self:
#             if rec.task_id and rec.task_id.project_id != rec.project_id:
#                 raise ValidationError(
#                     "Selected task does not belong to the selected project."
#                 )
#
#     def _is_timesheet_allowed_state(self):
#         # We allow syncing in these states
#         allowed_states = ['confirmed', 'done', 'approved']
#         return self.state in allowed_states
#
#     def _prepare_timesheet_vals(self):
#         self.ensure_one()
#         if not self._is_timesheet_allowed_state() or self.time_spent_hours <= 0:
#             return None
#
#         project = self.project_id
#         task = self.task_id
#         analytic_account = project.analytic_account_id if project.analytic_account_id else False
#
#         # Note: You can now set WHT on sales order lines if needed as per your workflow
#         sale_line = task.sale_line_id if task else False
#
#         return {
#             'name': self.description or self.name or "Work Activity",
#             'employee_id': self.employee_id.id,
#             'project_id': project.id,
#             'task_id': task.id if task else False,
#             'account_id': analytic_account.id if analytic_account else False,
#             'unit_amount': self.time_spent_hours,
#             'date': self.start_datetime.date() if self.start_datetime else fields.Date.today(),
#             'sale_line_id': sale_line.id if sale_line else False,
#             'employee_daily_activity_id': self.id,
#         }
#
#     def _sync_timesheet(self):
#         AnalyticLine = self.env['account.analytic.line']
#         for rec in self:
#             vals = rec._prepare_timesheet_vals()
#             if not vals:
#                 if rec.timesheet_id:
#                     rec.timesheet_id.with_context(force_timesheet_sync=True).unlink()
#                     rec.timesheet_id = False
#                 continue
#             if rec.timesheet_id:
#                 rec.timesheet_id.with_context(force_timesheet_sync=True).write(vals)
#             else:
#                 ts = AnalyticLine.with_context(force_timesheet_sync=True).create(vals)
#                 rec.timesheet_id = ts.id
#
#     def action_confirm(self):
#         res = super().action_confirm()
#         self.with_context(force_timesheet_sync=True)._sync_timesheet()
#         return res
#
#     def write(self, vals):
#         # REMOVED: The ValidationError block that checked for 'confirmed' state
#         res = super().write(vals)
#
#         # Trigger sync if relevant fields change, even if already confirmed
#         trigger_fields = [
#             'project_id', 'task_id', 'start_datetime', 'end_datetime',
#             'employee_id', 'description', 'time_spent_hours', 'state'
#         ]
#         if any(field in vals for field in trigger_fields):
#             self.with_context(force_timesheet_sync=True)._sync_timesheet()
#         return res
#
#     def unlink(self):
#         timesheets = self.mapped('timesheet_id')
#         res = super().unlink()
#         if timesheets:
#             timesheets.with_context(force_timesheet_sync=True).unlink()
#         return res
#
#
# # =====================================================
# # OVERTIME TIMESHEET EXTENSION
# # =====================================================
# class EmployeeOvertimeTimesheet(models.Model):
#     _inherit = 'employee.overtime'
#
#     timesheet_id = fields.Many2one(
#         'account.analytic.line',
#         string="Timesheet",
#         readonly=True,
#         copy=False
#     )
#
#     def _is_timesheet_allowed_state(self):
#         return self.state == 'confirmed'
#
#     def _prepare_timesheet_vals(self):
#         self.ensure_one()
#         if not self._is_timesheet_allowed_state() or self.daily_overtime_hours <= 0 or not self.project_id:
#             return None
#
#         analytic_account = self.project_id.analytic_account_id if self.project_id.analytic_account_id else False
#
#         return {
#             'name': self.description or self.activity_name or "Overtime Activity",
#             'employee_id': self.employee_id.id,
#             'project_id': self.project_id.id,
#             'task_id': False,
#             'account_id': analytic_account.id if analytic_account else False,
#             'unit_amount': self.daily_overtime_hours,
#             'date': self.start_datetime.date() if self.start_datetime else fields.Date.today(),
#             'employee_overtime_id': self.id,
#         }
#
#     def _sync_timesheet(self):
#         AnalyticLine = self.env['account.analytic.line']
#         for rec in self:
#             vals = rec._prepare_timesheet_vals()
#             if not vals:
#                 if rec.timesheet_id:
#                     rec.timesheet_id.with_context(force_timesheet_sync=True).unlink()
#                     rec.timesheet_id = False
#                 continue
#             if rec.timesheet_id:
#                 rec.timesheet_id.with_context(force_timesheet_sync=True).write(vals)
#             else:
#                 ts = AnalyticLine.with_context(force_timesheet_sync=True).create(vals)
#                 rec.timesheet_id = ts.id
#
#     def action_confirm(self):
#         res = super().action_confirm()
#         self.with_context(force_timesheet_sync=True)._sync_timesheet()
#         return res
#
#     def write(self, vals):
#         # REMOVED: The ValidationError block that checked for 'confirmed' state
#         res = super().write(vals)
#
#         trigger_fields = [
#             'project_id', 'start_datetime', 'end_datetime',
#             'employee_id', 'description', 'daily_overtime_hours', 'state'
#         ]
#         if any(field in vals for field in trigger_fields):
#             self.with_context(force_timesheet_sync=True)._sync_timesheet()
#         return res
#
#     def unlink(self):
#         timesheets = self.mapped('timesheet_id')
#         res = super().unlink()
#         if timesheets:
#             timesheets.with_context(force_timesheet_sync=True).unlink()
#         return res
#
#
# # =====================================================
# # REVERSE LINK FIELDS
# # =====================================================
# class AccountAnalyticLine(models.Model):
#     _inherit = 'account.analytic.line'
#
#     employee_daily_activity_id = fields.Many2one(
#         'employee.daily.activity',
#         string="Daily Activity",
#         index=True,
#         ondelete='set null'
#     )
#     employee_overtime_id = fields.Many2one(
#         'employee.overtime',
#         string="Overtime Entry",
#         index=True,
#         ondelete='set null'
#     )