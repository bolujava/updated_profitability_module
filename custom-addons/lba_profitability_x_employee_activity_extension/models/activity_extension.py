from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, time
import logging

_logger = logging.getLogger(__name__)


# =====================================================
# DAILY ACTIVITY TIMESHEET BRIDGE
# =====================================================
class EmployeeDailyActivityBridge(models.Model):
    _inherit = 'employee.daily.activity'

    task_id = fields.Many2one(
        'project.task',
        string='Task',
        domain="[('project_id','=',project_id)]"
    )

    timesheet_id = fields.Many2one(
        'account.analytic.line',
        string="Timesheet",
        readonly=True,
        copy=False
    )

    # -------------------------
    # Timesheet preparation (GUARANTEES NO BROKEN DATA)
    # -------------------------
    def _prepare_timesheet_vals(self):
        self.ensure_one()

        # Guardrail 1: State Check
        if self.state not in ['confirmed', 'done', 'approved']:
            return None

        # Guardrail 2: Hours Check
        hours = self.time_spent_hours
        if hours <= 0:
            return None

        # Guardrail 3: THE FIX - No project or No Analytic Account = No Timesheet
        if not self.project_id or not self.project_id.analytic_account_id:
            _logger.info("Activity %s: No Project/Analytic Account. Skipping timesheet creation.", self.id)
            return None

        project = self.project_id
        task = self.task_id
        analytic_account = project.analytic_account_id

        vals = {
            'name': self.description or self.name or "Work Activity",
            'employee_id': self.employee_id.id,
            'project_id': project.id,
            'task_id': task.id if task else False,
            'account_id': analytic_account.id,  # Guaranteed to be valid now
            'unit_amount': hours,
            'date': self.start_datetime.date() if self.start_datetime else fields.Date.today(),
        }

        if task and task.sale_line_id:
            vals['sale_line_id'] = task.sale_line_id.id

        return vals

    # -------------------------
    # Sync timesheet
    # -------------------------
    # def _sync_timesheet(self):
    #     AnalyticLine = self.env['account.analytic.line']
    #     bypass_ctx = {
    #         'force_timesheet_sync': True,
    #         'bypass_lock': True,
    #         'from_activity_timesheet_sync': True
    #     }
    #
    #     for rec in self:
    #         vals = rec._prepare_timesheet_vals()
    #
    #         # If no valid project/analytic found, we cleanup any existing timesheet and STOP.
    #         if not vals:
    #             if rec.timesheet_id:
    #                 rec.timesheet_id.with_context(**bypass_ctx).unlink()
    #                 rec.with_context(**bypass_ctx).write({'timesheet_id': False})
    #             continue
    #
    #         # Update or Create
    #         if rec.timesheet_id:
    #             rec.timesheet_id.with_context(**bypass_ctx).write(vals)
    #             timesheet = rec.timesheet_id
    #         else:
    #             timesheet = AnalyticLine.with_context(**bypass_ctx).create(vals)
    #             rec.with_context(**bypass_ctx).write({'timesheet_id': timesheet.id})
    #
    #         # Recompute delivery for Sales Orders
    #         if timesheet.sale_line_id:
    #             try:
    #                 timesheet.sale_line_id.with_context(**bypass_ctx)._compute_qty_delivered()
    #             except:
    #                 pass
    def _sync_timesheet(self):
        AnalyticLine = self.env['account.analytic.line']
        bypass_ctx = {
            'force_timesheet_sync': True,
            'bypass_lock': True,
            'from_activity_timesheet_sync': True
        }
        for rec in self:
            vals = rec._prepare_timesheet_vals()
            if not vals:
                if rec.timesheet_id:
                    rec.timesheet_id.sudo().with_context(**bypass_ctx).unlink()
                    rec.with_context(**bypass_ctx).write({'timesheet_id': False})
                continue
            if rec.timesheet_id:
                rec.timesheet_id.sudo().with_context(**bypass_ctx).write(vals)
                timesheet = rec.timesheet_id
            else:
                timesheet = AnalyticLine.sudo().with_context(**bypass_ctx).create(vals)
                rec.with_context(**bypass_ctx).write({'timesheet_id': timesheet.id})

            if timesheet.sale_line_id:
                try:
                    timesheet.sale_line_id.sudo().with_context(**bypass_ctx)._compute_qty_delivered()
                except:
                    pass


    # -------------------------
    # Confirm override
    # -------------------------
    def action_confirm(self):
        res = super().action_confirm()
        self.with_context(bypass_lock=True)._sync_timesheet()
        return res

    # -------------------------
    # Write override
    # -------------------------
    def write(self, vals):
        if self.env.context.get('force_timesheet_sync') or self.env.context.get('bypass_lock'):
            return super().write(vals)

        for rec in self:
            if rec.state == 'confirmed':
                if set(vals.keys()) == {'state'}:
                    continue
                raise ValidationError("Confirmed activities cannot be edited!")

        res = super().write(vals)

        trigger_fields = [
            'project_id', 'task_id', 'start_datetime', 'end_datetime',
            'employee_id', 'description', 'time_spent_hours', 'state'
        ]
        if any(field in vals for field in trigger_fields):
            self.with_context(bypass_lock=True)._sync_timesheet()

        return res

    # -------------------------
    # Delete override
    # -------------------------
    def unlink(self):
        timesheets = self.mapped('timesheet_id')
        res = super().unlink()
        if timesheets:
            timesheets.with_context(force_timesheet_sync=True, bypass_lock=True).unlink()
        return res


# =====================================================
# OVERTIME TIMESHEET BRIDGE
# =====================================================
class EmployeeOvertimeBridge(models.Model):
    _inherit = 'employee.overtime'

    task_id = fields.Many2one(
        'project.task',
        string='Task',
        domain="[('project_id','=',project_id)]"
    )

    timesheet_id = fields.Many2one(
        'account.analytic.line',
        string="Timesheet",
        readonly=True,
        copy=False
    )

    def _prepare_timesheet_vals(self):
        self.ensure_one()

        if self.state != 'confirmed':
            return None

        hours = self.daily_overtime_hours
        if hours <= 0:
            return None

        # Guardrail: Overtime MUST have a project/analytic account to sync
        if not self.project_id or not self.project_id.analytic_account_id:
            return None

        project = self.project_id
        analytic_account = project.analytic_account_id

        return {
            'name': self.description or self.activity_name or "Overtime Activity",
            'employee_id': self.employee_id.id,
            'project_id': project.id,
            'task_id': self.task_id.id if self.task_id else False,
            'account_id': analytic_account.id,
            'unit_amount': hours,
            'date': self.start_datetime.date() if self.start_datetime else fields.Date.today(),
        }

    # def _sync_timesheet(self):
    #     AnalyticLine = self.env['account.analytic.line']
    #     bypass_ctx = {'force_timesheet_sync': True, 'bypass_lock': True}
    #
    #     for rec in self:
    #         vals = rec._prepare_timesheet_vals()
    #         if not vals:
    #             if rec.timesheet_id:
    #                 rec.timesheet_id.with_context(**bypass_ctx).unlink()
    #                 rec.with_context(**bypass_ctx).write({'timesheet_id': False})
    #             continue
    #
    #         if rec.timesheet_id:
    #             rec.timesheet_id.with_context(**bypass_ctx).write(vals)
    #         else:
    #             timesheet = AnalyticLine.with_context(**bypass_ctx).create(vals)
    #             rec.with_context(**bypass_ctx).write({'timesheet_id': timesheet.id})

    def _sync_timesheet(self):
        AnalyticLine = self.env['account.analytic.line']
        bypass_ctx = {
            'force_timesheet_sync': True,
            'bypass_lock': True,
            'from_activity_timesheet_sync': True
        }
        for rec in self:
            vals = rec._prepare_timesheet_vals()
            if not vals:
                if rec.timesheet_id:
                    rec.timesheet_id.sudo().with_context(**bypass_ctx).unlink()
                    rec.with_context(**bypass_ctx).write({'timesheet_id': False})
                continue
            if rec.timesheet_id:
                rec.timesheet_id.sudo().with_context(**bypass_ctx).write(vals)
                timesheet = rec.timesheet_id
            else:
                timesheet = AnalyticLine.sudo().with_context(**bypass_ctx).create(vals)
                rec.with_context(**bypass_ctx).write({'timesheet_id': timesheet.id})

            if timesheet.sale_line_id:
                try:
                    timesheet.sale_line_id.sudo().with_context(**bypass_ctx)._compute_qty_delivered()
                except:
                    pass

    def action_confirm(self):
        res = super().action_confirm()
        self.with_context(bypass_lock=True)._sync_timesheet()
        return res

    def write(self, vals):
        if self.env.context.get('force_timesheet_sync') or self.env.context.get('bypass_lock'):
            return super().write(vals)

        for rec in self:
            if rec.state == 'confirmed':
                if set(vals.keys()) == {'state'}:
                    continue
                raise ValidationError("Confirmed overtime entries cannot be edited!")

        res = super().write(vals)

        trigger_fields = [
            'project_id', 'start_datetime', 'end_datetime',
            'employee_id', 'description', 'daily_overtime_hours', 'state'
        ]
        if any(field in vals for field in trigger_fields):
            self.with_context(bypass_lock=True)._sync_timesheet()

        return res

    def unlink(self):
        timesheets = self.mapped('timesheet_id')
        res = super().unlink()
        if timesheets:
            timesheets.with_context(force_timesheet_sync=True, bypass_lock=True).unlink()
        return res