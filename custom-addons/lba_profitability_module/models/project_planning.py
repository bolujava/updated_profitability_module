# models/planning_slot.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    sale_line_id = fields.Many2one(
        'sale.order.line',
        string="Sales Order Line",
        domain="[('order_id.project_id', '=', project_id)]",
        store=True,
        help="The sales order line that created or funds this project/task."
    )
    task_id = fields.Many2one(
        'project.task',
        string="Task",
        domain="[('project_id', '=', project_id)]",
        store=True
    )
    training_id = fields.Many2one(
        'training.list',
        string="Training",
        store=True
    )
    start_datetime = fields.Datetime(
        string="Start Date",
        required=True
    )
    end_datetime = fields.Datetime(
        string="End Date",
        required=True
    )
    timesheet_ids = fields.One2many(
        'account.analytic.line',
        'planning_slot_id',
        string="Timesheets",
        readonly=True
    )
    progress = fields.Float(string="Progress (%)", related='task_id.progress', store=True)

    # ---------------------------------------------------------------------
    # ONCHANGE LOGIC
    # ---------------------------------------------------------------------

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """When project changes, auto-link its sale line and restrict tasks."""
        if not self.project_id:
            self.sale_line_id = False
            self.task_id = False
            return {'domain': {'task_id': [], 'sale_line_id': []}}

        return {
            'domain': {
                'task_id': [('project_id', '=', self.project_id.id)],
                'sale_line_id': [('order_id.project_id', '=', self.project_id.id)],
            }
        }

    @api.onchange('task_id')
    def _onchange_task_id(self):
        """If the selected task has a different sale line, update accordingly."""
        if self.task_id and self.task_id.sale_line_id:
            self.sale_line_id = self.task_id.sale_line_id.id

    # ---------------------------------------------------------------------
    # CONSTRAINTS
    # ---------------------------------------------------------------------

    # @api.constrains('start_datetime', 'end_datetime', 'employee_id')
    # def _check_no_overlap(self):
    #     for slot in self:
    #         if slot.start_datetime and slot.end_datetime and slot.employee_id:
    #             overlapping = self.search([
    #                 ('id', '!=', slot.id),
    #                 ('employee_id', '=', slot.employee_id.id),
    #                 ('start_datetime', '<', slot.end_datetime),
    #                 ('end_datetime', '>', slot.start_datetime),
    #             ])
    #             if overlapping:
    #                 raise ValidationError(_("This planning slot overlaps with existing slots for the same employee."))

    @api.constrains('start_datetime', 'end_datetime')
    def _check_datetime_validity(self):
        for slot in self:
            if slot.start_datetime and slot.end_datetime and slot.end_datetime <= slot.start_datetime:
                raise ValidationError(_("End Date must be after Start Date."))

    def _should_create_timesheet(self):
        """Check if conditions are met for timesheet creation"""
        return all([
            self.task_id,
            self.employee_id,
            self.start_datetime,
            self.end_datetime
        ])

    def _compute_slot_hours(self):
        """Compute hours from datetime range"""
        if not self.start_datetime or not self.end_datetime:
            return 0.0
        return (self.end_datetime - self.start_datetime).total_seconds() / 3600

    # def _prepare_timesheet_vals(self):
    #     """Prepare timesheet values"""
    #     slot_hours = self._compute_slot_hours()
    #     if slot_hours <= 0:
    #         return None
    #
    #     analytic_account = self.project_id.analytic_account_id if self.project_id else False
    #
    #     return {
    #         'project_id': self.project_id.id if self.project_id else False,
    #         'task_id': self.task_id.id,
    #         'employee_id': self.employee_id.id,
    #         'sale_line_id': self.sale_line_id.id if self.sale_line_id else False,
    #         'account_id': analytic_account.id if analytic_account else False,
    #         'date': self.start_datetime.date(),
    #         'unit_amount': slot_hours,
    #         'planning_slot_id': self.id,
    #         'name': f"Planned work on {self.task_id.name or (self.project_id.name if self.project_id else 'Unnamed Task')}",
    #     }
    #
    # def _sync_timesheet(self):
    #     """Sync timesheet for this slot"""
    #     try:
    #         if not self._should_create_timesheet():
    #             _logger.warning(f"Skipping timesheet sync for slot {self.id}. Missing required fields.")
    #             return
    #
    #         timesheet_vals = self._prepare_timesheet_vals()
    #         if not timesheet_vals:
    #             _logger.warning(f"Invalid timesheet values for slot {self.id}")
    #             return
    #
    #         # Handle existing timesheets
    #         if self.timesheet_ids:
    #             # Update first timesheet
    #             _logger.info(f"Updating timesheet {self.timesheet_ids[0].id} for slot {self.id}")
    #             self.timesheet_ids[0].write(timesheet_vals)
    #             # Remove extra timesheets if any
    #             if len(self.timesheet_ids) > 1:
    #                 _logger.info(f"Removing extra timesheets: {self.timesheet_ids[1:].ids}")
    #                 self.timesheet_ids[1:].unlink()
    #         else:
    #             # Create new timesheet
    #             _logger.info(f"Creating new timesheet for slot {self.id}")
    #             self.env['account.analytic.line'].create(timesheet_vals)
    #
    #     except Exception as e:
    #         _logger.error(f"Error syncing timesheet for planning slot {self.id}: {str(e)}")
    #         # Don't raise exception to avoid blocking the operation


    def _prepare_timesheet_vals(self):
        """Prepare timesheet values with strict guardrails."""
        self.ensure_one()
        slot_hours = self._compute_slot_hours()

        # Guardrail 1: No time recorded
        if slot_hours <= 0:
            return None

        # Guardrail 2: No Project or No Analytic Account linked to Project
        # This is the "Fix" to prevent the Mandatory Field error.
        if not self.project_id or not self.project_id.analytic_account_id:
            _logger.info("Planning Slot %s: No Analytic Account found, skipping timesheet.", self.id)
            return None

        analytic_account = self.project_id.analytic_account_id

        return {
            'project_id': self.project_id.id,
            'task_id': self.task_id.id if self.task_id else False,
            'employee_id': self.employee_id.id,
            'sale_line_id': self.sale_line_id.id if self.sale_line_id else False,
            'account_id': analytic_account.id,  # Guaranteed to exist now
            'date': self.start_datetime.date(),
            'unit_amount': slot_hours,
            'planning_slot_id': self.id,
            'name': f"Planned work on {self.task_id.name or self.project_id.name or 'Task'}",
        }

    # ---------------------------------------------------------------------
    # UPDATED SYNC LOGIC
    # ---------------------------------------------------------------------
    def _sync_timesheet(self):
        """Sync timesheet for this slot and handle cleanup."""
        try:
            # If basic info is missing, we can't even try to sync
            if not self._should_create_timesheet():
                if self.timesheet_ids:
                    self.timesheet_ids.unlink()
                return

            timesheet_vals = self._prepare_timesheet_vals()

            # IF VALS IS NONE: It means project is missing or analytic is empty.
            # We must NOT create a record, and we should delete any existing one.
            if not timesheet_vals:
                if self.timesheet_ids:
                    _logger.info("Removing timesheet for slot %s as it no longer meets analytic requirements.",
                                 self.id)
                    self.timesheet_ids.unlink()
                return

            # Handle existing timesheets
            if self.timesheet_ids:
                _logger.info(f"Updating timesheet {self.timesheet_ids[0].id} for slot {self.id}")
                self.timesheet_ids[0].write(timesheet_vals)
                if len(self.timesheet_ids) > 1:
                    self.timesheet_ids[1:].unlink()
            else:
                # Create new timesheet safely
                _logger.info(f"Creating new timesheet for slot {self.id}")
                self.env['account.analytic.line'].create(timesheet_vals)

        except Exception as e:
            _logger.error(f"Error syncing timesheet for planning slot {self.id}: {str(e)}")

        # ---------------------------------------------------------------------
        # OVERRIDES
        # ---------------------------------------------------------------------
        @api.model
        def create(self, vals_list):
            slots = super(PlanningSlot, self).create(vals_list)
            for slot in slots:
                if slot.task_id and slot.employee_id:
                    if slot.employee_id not in slot.task_id.assigned_employee_ids:
                        slot.task_id.write({'assigned_employee_ids': [(4, slot.employee_id.id)]})
                # Sync happens here, now protected by the check above
                slot._sync_timesheet()
            return slots

        def write(self, vals):
            result = super(PlanningSlot, self).write(vals)
            relevant_fields = ['start_datetime', 'end_datetime', 'task_id', 'project_id', 'sale_line_id', 'employee_id']
            if any(field in vals for field in relevant_fields):
                for slot in self:
                    slot._sync_timesheet()
            return result



    @api.model
    def create(self, vals_list):
        """Sync planner slot with timesheet on creation."""
        _logger.info(f"Creating planning slots with vals: {vals_list}")

        # Create slots first
        slots = super(PlanningSlot, self).create(vals_list)

        # Sync timesheets in a separate transaction to avoid rollbacks
        for slot in slots:
            # Add employee to task's assigned employees
            if slot.task_id and slot.employee_id:
                if slot.employee_id not in slot.task_id.assigned_employee_ids:
                    slot.task_id.write({
                        'assigned_employee_ids': [(4, slot.employee_id.id)]
                    })

            # Sync timesheet
            slot._sync_timesheet()

        return slots

    def write(self, vals):
        """Sync changes to related timesheets."""
        _logger.info(f"Updating planning slots {self.ids} with vals: {vals}")

        # Store old values for comparison
        old_values = {}
        for slot in self:
            old_values[slot.id] = {
                'task_id': slot.task_id.id,
                'employee_id': slot.employee_id.id,
                'start_datetime': slot.start_datetime,
                'end_datetime': slot.end_datetime,
                'project_id': slot.project_id.id if slot.project_id else False,
                'sale_line_id': slot.sale_line_id.id if slot.sale_line_id else False,
            }

        # Perform the write operation
        result = super(PlanningSlot, self).write(vals)

        # Check if relevant fields changed
        relevant_fields = ['start_datetime', 'end_datetime', 'task_id', 'project_id', 'sale_line_id', 'employee_id']
        if any(field in vals for field in relevant_fields):
            for slot in self:
                try:
                    slot._sync_timesheet()
                except Exception as e:
                    _logger.error(f"Failed to sync timesheet for slot {slot.id}: {str(e)}")
                    # Continue with other slots even if one fails

        return result

    def unlink(self):
        """Clean up timesheets when planning slot is deleted."""
        _logger.info(f"Attempting to unlink planning slots: {self.ids}")

        # Store timesheet info before deletion
        timesheet_info = []
        for slot in self:
            if slot.timesheet_ids:
                timesheet_info.append({
                    'slot_id': slot.id,
                    'timesheet_ids': slot.timesheet_ids.ids
                })

        # Unlink planning_slot_id from timesheets first
        all_timesheets = self.mapped('timesheet_ids')
        if all_timesheets:
            _logger.info(f"Unlinking planning_slot_id from timesheets: {all_timesheets.ids}")
            all_timesheets.write({'planning_slot_id': False})

        # Proceed with deletion
        result = super(PlanningSlot, self).unlink()
        _logger.info(f"Successfully unlinked planning slots: {self.ids}")

        return result

    def action_create_task(self):
        """Open a task creation form tied to this project and sale line."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.project_id.id,
                'default_sale_line_id': self.sale_line_id.id,
                'default_user_ids': [(6, 0, [self.employee_id.user_id.id])] if self.employee_id else [],
            }
        }

    def action_force_timesheet_sync(self):
        """Manual action to force timesheet synchronization"""
        for slot in self:
            slot._sync_timesheet()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Timesheet Sync'),
                'message': _('Timesheet synchronization completed.'),
                'type': 'success',
                'sticky': False,
            }
        }

# ---------------------------------------------------------------------
# LINKED TIMESHEET MODEL
# ---------------------------------------------------------------------

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    planning_slot_id = fields.Many2one(
        'planning.slot',
        string="Planning Slot",
        index=True,
        ondelete='set null'
    )
    sale_line_id = fields.Many2one(comodel_name='sale.order.line', string="Sales Order Item", index=True,
                                   ondelete='set null')

    # The cost should come from the task's job rate, not the employee's
    cost_per_hour = fields.Float(
        string="Cost/Hour",
        compute="_compute_task_cost",
        store=True
    )

    @api.depends('task_id.job_rate_id')
    def _compute_task_cost(self):
        for timesheet in self:
            if timesheet.task_id and timesheet.task_id.job_rate_id:
                timesheet.cost_per_hour = timesheet.task_id.job_rate_id.cost_rate
            else:
                timesheet.cost_per_hour = 0.0
