# # -*- coding: utf-8 -*-
# from odoo import models, fields, api, _
# import logging
#
# _logger = logging.getLogger(__name__)
#
#
# class ProjectResourceProfit(models.Model):
#     _name = 'project.resource.profit'
#     _description = 'Per-resource profitability row for a Project'
#     _order = 'employee_id'
#
#     project_id = fields.Many2one('project.project', string='Project', required=True, ondelete='cascade')
#     employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
#     selling_price_per_hour = fields.Float(string='Selling Price / Hour', digits='Product Price')
#     cost_per_hour = fields.Float(string='Cost / Hour', digits='Product Price')
#     expected_hours = fields.Float(string='Expected / Assigned Hours')  # from task.planned_hours
#     time_spent = fields.Float(string='Time Spent (Timesheets)')  # from tracker activities
#     other_expenses = fields.Monetary(string='Other Expenses', currency_field='company_currency_id')
#     cost_incurred = fields.Monetary(string='Cost Incurred', currency_field='company_currency_id')
#     total_cost = fields.Monetary(string='Total Cost', currency_field='company_currency_id')
#     selling_total = fields.Monetary(string='Selling Amount', currency_field='company_currency_id')
#     profit = fields.Monetary(string='Profit', currency_field='company_currency_id')
#     profit_margin = fields.Float(string='Profit Margin (%)')
#     company_currency_id = fields.Many2one('res.currency', string='Currency', related='project_id.currency_id',
#                                           readonly=True)
#
#     @api.model
#     def _calc_for_project(self, project):
#         if not project or not project.exists():
#             return []
#
#         employee_data = {}
#
#         # 1. ONLY GATHER EMPLOYEES WHO ACTUALLY LOGGED TIMESHEETS
#         timesheets = self.env['account.analytic.line'].search([('project_id', '=', project.id)])
#
#         # If no one has tracked any hours yet, return an empty set cleanly
#         if not timesheets:
#             return []
#
#         for ts in timesheets:
#             if not ts.employee_id:
#                 continue
#
#             emp_id = ts.employee_id.id
#             if emp_id not in employee_data:
#                 # Find an active task assigned to this specific employee in this project to get their job rate
#                 matched_task = project.task_ids.filtered(
#                     lambda t: t.user_id.employee_id.id == emp_id or emp_id in t.assigned_employee_ids.ids
#                 )
#                 # Use the first matched task found, or fall back gracefully
#                 active_task = matched_task[0] if matched_task else False
#
#                 # Resolve the internal cost rate from the task's Job Rate configuration
#                 internal_cost_rate = 0.0
#                 if active_task and getattr(active_task, 'job_rate_id', False):
#                     internal_cost_rate = getattr(active_task.job_rate_id, 'hourly_rate', 0.0)
#
#                 # Determine billing/selling rate
#                 billing_rate = 0.0
#                 if active_task and active_task.sale_line_id:
#                     billing_rate = active_task.sale_line_id.price_unit
#                 elif ts.so_line:
#                     billing_rate = ts.so_line.price_unit
#                 elif project.sale_order_id and project.sale_order_id.order_line:
#                     first_line = project.sale_order_id.order_line.filtered(lambda l: not l.display_type)
#                     if first_line:
#                         billing_rate = first_line[0].price_unit
#
#                 employee_data[emp_id] = {
#                     'employee_id': emp_id,
#                     'selling_price_per_hour': billing_rate,
#                     'cost_per_hour': internal_cost_rate,
#                     'expected_hours': 0.0,
#                     'time_spent': 0.0,
#                 }
#
#             # Accumulate their actual tracked execution hours
#             employee_data[emp_id]['time_spent'] += ts.unit_amount
#
#         # 2. NOW MAP EXPECTED ASSIGNED HOURS ONLY FOR THE ACTIVE TIMESHEET EMPLOYEES
#         if project.task_ids:
#             for task in project.task_ids:
#                 # Check primary user
#                 primary_emp = task.user_id.employee_id if getattr(task, 'user_id', False) else False
#
#                 # Check all assigned employees if multi-assignment is enabled
#                 assigned_emp_ids = task.assigned_employee_ids.ids if getattr(task, 'assigned_employee_ids',
#                                                                              False) else []
#                 if primary_emp and primary_emp.id not in assigned_emp_ids:
#                     assigned_emp_ids.append(primary_emp.id)
#
#                 for emp_id in assigned_emp_ids:
#                     # CRITICAL: Only add expected hours if they have an active timesheet entry!
#                     if emp_id in employee_data:
#                         # If the task has multiple people, let Leg Two handle the split cleanly.
#                         # For baseline, we accumulate the planned hours.
#                         if not getattr(task, 'assigned_employee_ids', False) or len(task.assigned_employee_ids) <= 1:
#                             employee_data[emp_id]['expected_hours'] += task.planned_hours or 0.0
#
#         # 3. BUILD THE FINAL CONSOLIDATED DATA ROWS
#         rows = []
#         for emp_id, data in employee_data.items():
#             selling_rate = data['selling_price_per_hour']
#             cost_rate = data['cost_per_hour']
#             expected_hours = data['expected_hours']
#             time_spent = data['time_spent']
#
#             # If it's a fixed flat rate milestone contract, give full revenue allocation to the active earner
#             if project.sale_order_id:
#                 selling_total = project.total_revenue / len(employee_data)
#             else:
#                 selling_total = expected_hours * selling_rate
#
#             # Apply true cost calculation
#             cost_incurred = time_spent * cost_rate
#             profit = selling_total - cost_incurred
#             margin = (profit / selling_total * 100) if selling_total > 0 else 0.0
#
#             rows.append({
#                 'project_id': project.id,
#                 'employee_id': emp_id,
#                 'selling_price_per_hour': selling_rate,
#                 'cost_per_hour': cost_rate,
#                 'expected_hours': expected_hours,
#                 'time_spent': time_spent,
#                 'selling_total': selling_total,
#                 'cost_incurred': cost_incurred,
#                 'total_cost': cost_incurred,
#                 'profit': profit,
#                 'profit_margin': margin,
#             })
#         return rows
#
#
# class ProjectProject(models.Model):
#     _inherit = 'project.project'
#
#     def _sync_resource_profit(self):
#         if self.env.context.get('_rpm_sync_in_progress'):
#             return True
#
#         ResourceProfit = self.env['project.resource.profit']
#         self = self.with_context(_rpm_sync_in_progress=True)
#
#         for project in self:
#             try:
#                 old = ResourceProfit.search([('project_id', '=', project.id)])
#                 if old:
#                     old.unlink()
#
#                 rows = ResourceProfit._calc_for_project(project)
#                 if rows:
#                     for r in rows:
#                         ResourceProfit.create(r)
#             except Exception:
#                 _logger.exception("Failed to sync project.resource.profit for project %s", project.id)
#
#         return True
#
#     def action_open_resource_profitability(self):
#         self._sync_resource_profit()
#         return {
#             'name': 'Resource Profitability',
#             'type': 'ir.actions.act_window',
#             'res_model': 'project.resource.profit',
#             'view_mode': 'tree',
#             'view_id': self.env.ref('lba_profitability_module.view_project_resource_profit_tree').id,
#             'domain': [('project_id', 'in', self.ids)],
#             'context': {'default_project_id': self.id},
#         }
#
#
# # -------------------------
# # RELATIONAL MODEL TRIGGERS
# # -------------------------
# class ProjectTask(models.Model):
#     _inherit = 'project.task'
#
#     def write(self, vals):
#         old_planned = {t.id: float(t.planned_hours or 0.0) for t in self}
#         res = super(ProjectTask, self).write(vals)
#
#         to_sync_projects = self.env['project.project']
#         for t in self:
#             old = old_planned.get(t.id, 0.0)
#             new = float(t.planned_hours or 0.0)
#             if abs(new - old) > 0.0001 or 'user_id' in vals or 'job_rate_id' in vals:
#                 if t.project_id:
#                     to_sync_projects |= t.project_id
#
#         if to_sync_projects:
#             to_sync_projects._sync_resource_profit()
#         return res
#
#
# class SaleOrderLine(models.Model):
#     _inherit = 'sale.order.line'
#
#     def write(self, vals):
#         old_qty = {l.id: float(l.qty_delivered or 0.0) for l in self}
#         res = super(SaleOrderLine, self).write(vals)
#
#         to_sync_projects = self.env['project.project']
#         for l in self:
#             try:
#                 new_qty = float(l.qty_delivered or 0.0)
#             except Exception:
#                 new_qty = 0.0
#             old = old_qty.get(l.id, 0.0)
#             if abs(new_qty - old) > 0.0001 or 'price_unit' in vals:
#                 proj = False
#                 if l.order_id and getattr(l.order_id, 'project_id', False):
#                     proj = l.order_id.project_id
#                 if not proj:
#                     tasks = l.task_ids
#                     if tasks:
#                         proj = tasks[0].project_id
#                 if proj:
#                     to_sync_projects |= proj
#
#         if to_sync_projects:
#             to_sync_projects._sync_resource_profit()
#         return res
#
#
# class AccountAnalyticLine(models.Model):
#     _inherit = 'account.analytic.line'
#
#     so_line = fields.Many2one(
#         'sale.order.line',
#         string="Sales Order Line",
#         index=True,
#         ondelete='set null'
#     )
#
#     @api.model_create_multi
#     def create(self, vals_list):
#         recs = super(AccountAnalyticLine, self).create(vals_list)
#         projects = recs.mapped('project_id')
#         if projects:
#             projects._sync_resource_profit()
#         return recs
#
#     def write(self, vals):
#         interesting = {'unit_amount', 'task_id', 'employee_id', 'sale_line_id'}
#         perform = any(k in vals for k in interesting)
#         res = super(AccountAnalyticLine, self).write(vals)
#         if perform:
#             projects = self.mapped('project_id')
#             if projects:
#                 projects._sync_resource_profit()
#         return res


# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ProjectResourceProfit(models.Model):
    _name = 'project.resource.profit'
    _description = 'Per-resource profitability row for a Project'
    _order = 'employee_id'

    project_id = fields.Many2one('project.project', string='Project', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    selling_price_per_hour = fields.Float(string='Selling Price / Hour', digits='Product Price')
    cost_per_hour = fields.Float(string='Cost / Hour', digits='Product Price')
    expected_hours = fields.Float(string='Expected / Assigned Hours')  # from task.planned_hours
    time_spent = fields.Float(string='Time Spent (Timesheets)')  # from tracker activities
    other_expenses = fields.Monetary(string='Other Expenses', currency_field='company_currency_id')
    cost_incurred = fields.Monetary(string='Cost Incurred', currency_field='company_currency_id')
    total_cost = fields.Monetary(string='Total Cost', currency_field='company_currency_id')
    selling_total = fields.Monetary(string='Selling Amount', currency_field='company_currency_id')
    profit = fields.Monetary(string='Profit', currency_field='company_currency_id')
    profit_margin = fields.Float(string='Profit Margin (%)')
    company_currency_id = fields.Many2one('res.currency', string='Currency', related='project_id.currency_id',
                                          readonly=True)

    @api.model
    def _calc_for_project(self, project):
        if not project or not project.exists():
            return []

        employee_data = {}

        # 1. ONLY GATHER EMPLOYEES WHO ACTUALLY LOGGED TIMESHEETS
        timesheets = self.env['account.analytic.line'].search([('project_id', '=', project.id)])

        # If no one has tracked any hours yet, return an empty set cleanly
        if not timesheets:
            return []

        for ts in timesheets:
            if not ts.employee_id:
                continue

            emp_id = ts.employee_id.id
            if emp_id not in employee_data:
                # Find an active task assigned to this specific employee in this project to get their job rate
                matched_task = project.task_ids.filtered(
                    lambda t: t.user_id.employee_id.id == emp_id or emp_id in t.assigned_employee_ids.ids
                )
                # Use the first matched task found, or fall back gracefully
                active_task = matched_task[0] if matched_task else False

                # Resolve the internal cost rate from the task's Job Rate configuration
                internal_cost_rate = 0.0
                if active_task and getattr(active_task, 'job_rate_id', False):
                    internal_cost_rate = getattr(active_task.job_rate_id, 'hourly_rate', 0.0)

                # Determine billing/selling rate
                billing_rate = 0.0
                if active_task and active_task.sale_line_id:
                    billing_rate = active_task.sale_line_id.price_unit
                elif ts.so_line:
                    billing_rate = ts.so_line.price_unit
                elif project.sale_order_id and project.sale_order_id.order_line:
                    first_line = project.sale_order_id.order_line.filtered(lambda l: not l.display_type)
                    if first_line:
                        # Keep original baseline line pricing fallback reference intact
                        billing_rate = first_line[0].price_unit

                employee_data[emp_id] = {
                    'employee_id': emp_id,
                    'selling_price_per_hour': billing_rate,
                    'cost_per_hour': internal_cost_rate,
                    'expected_hours': 0.0,
                    'time_spent': 0.0,
                }

            # Accumulate their actual tracked execution hours
            employee_data[emp_id]['time_spent'] += ts.unit_amount

        # 2. NOW MAP EXPECTED ASSIGNED HOURS ONLY FOR THE ACTIVE TIMESHEET EMPLOYEES
        if project.task_ids:
            for task in project.task_ids:
                # Check primary user
                primary_emp = task.user_id.employee_id if getattr(task, 'user_id', False) else False

                # Check all assigned employees if multi-assignment is enabled
                assigned_emp_ids = task.assigned_employee_ids.ids if getattr(task, 'assigned_employee_ids',
                                                                             False) else []
                if primary_emp and primary_emp.id not in assigned_emp_ids:
                    assigned_emp_ids.append(primary_emp.id)

                for emp_id in assigned_emp_ids:
                    # CRITICAL: Only add expected hours if they have an active timesheet entry!
                    if emp_id in employee_data:
                        # If the task has multiple people, let Leg Two handle the split cleanly.
                        # For baseline, we accumulate the planned hours.
                        if not getattr(task, 'assigned_employee_ids', False) or len(task.assigned_employee_ids) <= 1:
                            employee_data[emp_id]['expected_hours'] += task.planned_hours or 0.0

        # 3. BUILD THE FINAL CONSOLIDATED DATA ROWS
        rows = []

        # Calculate the total planned proportional budget weight across the active team
        total_planned_value = sum(
            data['expected_hours'] * data['selling_price_per_hour'] for data in employee_data.values()) or 1.0

        for emp_id, data in employee_data.items():
            selling_rate = data['selling_price_per_hour']
            cost_rate = data['cost_per_hour']
            expected_hours = data['expected_hours']
            time_spent = data['time_spent']

            # Calculate this specific resource's planned budget value
            resource_planned_value = expected_hours * selling_rate

            if project.sale_order_id:
                # Split the contract total pool based on their Job Rate allocation weight
                contract_total = getattr(project, 'total_revenue', project.sale_order_id.amount_total)
                selling_total = contract_total * (resource_planned_value / total_planned_value)

                # Derive a clean operational hourly rate for display based on the allocation slice
                display_selling_price = selling_total / expected_hours if expected_hours > 0 else selling_rate
            else:
                selling_total = resource_planned_value
                display_selling_price = selling_rate

            # Apply true cost calculation
            cost_incurred = time_spent * cost_rate
            profit = selling_total - cost_incurred
            margin = (profit / selling_total * 100) if selling_total > 0 else 0.0

            rows.append({
                'project_id': project.id,
                'employee_id': emp_id,
                'selling_price_per_hour': display_selling_price,
                'cost_per_hour': cost_rate,
                'expected_hours': expected_hours,
                'time_spent': time_spent,
                'selling_total': selling_total,
                'cost_incurred': cost_incurred,
                'total_cost': cost_incurred,
                'profit': profit,
                'profit_margin': margin,
            })
        return rows


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _sync_resource_profit(self):
        if self.env.context.get('_rpm_sync_in_progress'):
            return True

        ResourceProfit = self.env['project.resource.profit']
        self = self.with_context(_rpm_sync_in_progress=True)

        for project in self:
            try:
                old = ResourceProfit.search([('project_id', '=', project.id)])
                if old:
                    old.unlink()

                rows = ResourceProfit._calc_for_project(project)
                if rows:
                    for r in rows:
                        ResourceProfit.create(r)
            except Exception:
                _logger.exception("Failed to sync project.resource.profit for project %s", project.id)

        return True

    def action_open_resource_profitability(self):
        self._sync_resource_profit()
        return {
            'name': 'Resource Profitability',
            'type': 'ir.actions.act_window',
            'res_model': 'project.resource.profit',
            'view_mode': 'tree',
            'view_id': self.env.ref('lba_profitability_module.view_project_resource_profit_tree').id,
            'domain': [('project_id', 'in', self.ids)],
            'context': {'default_project_id': self.id},
        }


# -------------------------
# RELATIONAL MODEL TRIGGERS
# -------------------------
class ProjectTask(models.Model):
    _inherit = 'project.task'

    def write(self, vals):
        old_planned = {t.id: float(t.planned_hours or 0.0) for t in self}
        res = super(ProjectTask, self).write(vals)

        to_sync_projects = self.env['project.project']
        for t in self:
            old = old_planned.get(t.id, 0.0)
            new = float(t.planned_hours or 0.0)
            if abs(new - old) > 0.0001 or 'user_id' in vals or 'job_rate_id' in vals:
                if t.project_id:
                    to_sync_projects |= t.project_id

        if to_sync_projects:
            to_sync_projects._sync_resource_profit()
        return res


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def write(self, vals):
        old_qty = {l.id: float(l.qty_delivered or 0.0) for l in self}
        res = super(SaleOrderLine, self).write(vals)

        to_sync_projects = self.env['project.project']
        for l in self:
            try:
                new_qty = float(l.qty_delivered or 0.0)
            except Exception:
                new_qty = 0.0
            old = old_qty.get(l.id, 0.0)
            if abs(new_qty - old) > 0.0001 or 'price_unit' in vals:
                proj = False
                if l.order_id and getattr(l.order_id, 'project_id', False):
                    proj = l.order_id.project_id
                if not proj:
                    tasks = l.task_ids
                    if tasks:
                        proj = tasks[0].project_id
                if proj:
                    to_sync_projects |= proj

        if to_sync_projects:
            to_sync_projects._sync_resource_profit()
        return res


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    so_line = fields.Many2one(
        'sale.order.line',
        string="Sales Order Line",
        index=True,
        ondelete='set null'
    )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super(AccountAnalyticLine, self).create(vals_list)
        projects = recs.mapped('project_id')
        if projects:
            projects._sync_resource_profit()
        return recs

    def write(self, vals):
        interesting = {'unit_amount', 'task_id', 'employee_id', 'sale_line_id'}
        perform = any(k in vals for k in interesting)
        res = super(AccountAnalyticLine, self).write(vals)
        if perform:
            projects = self.mapped('project_id')
            if projects:
                projects._sync_resource_profit()
        return res