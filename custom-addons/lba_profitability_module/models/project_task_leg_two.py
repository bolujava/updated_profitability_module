# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ProjectTaskLegTwo(models.Model):
    _inherit = 'project.task'

    @api.depends('project_id.sale_order_id', 'job_rate_id')
    def _compute_sale_line_id(self):
        for task in self:
            if task.project_id and task.project_id.sale_order_id and task.job_rate_id:

                matching_so_line = task.project_id.sale_order_id.order_line.filtered(
                    lambda l: l.product_id == task.job_rate_id.product_id and not l.display_type
                )

                if matching_so_line:
                    task.sale_line_id = matching_so_line[0].id
                    task.sale_order_id = task.project_id.sale_order_id.id
                    _logger.info("Leg 2 Match Found: Task '%s' matched to SO Line ID %s", task.name,
                                 matching_so_line[0].id)
                    continue

            if task.project_id and getattr(task.project_id, 'sale_line_id', False):
                task.sale_line_id = task.project_id.sale_line_id.id
                task.sale_order_id = task.project_id.sale_order_id.id
            else:
                task.sale_line_id = False
                task.sale_order_id = False



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

    timesheet_cost = fields.Float(string="Timesheet Cost", readonly=True)

    profitability_score = fields.Float(
        string="Performance Efficiency (%)",
        readonly=True
    )

    selling_price_per_hour = fields.Float(string="Selling Price/Hour", readonly=True)
    cost_per_hour = fields.Float(string="Cost/Hour", readonly=True)
    total_hours = fields.Float(string="Total Hours (Timesheet)", readonly=True)
    total_revenue = fields.Float(string="Total Revenue", readonly=True)
    total_cost = fields.Float(string="Total Cost", readonly=True)
    total_profit = fields.Float(string="Profit", readonly=True)
    profit_margin = fields.Float(string="Profit Margin (%)", readonly=True)

    team_lead_id = fields.Many2one(
        'hr.employee',
        string="Team Lead",
        readonly=True,
    )

    def _compute_public_employee_fields(self):
        real_employees = self.env['hr.employee'].browse(self.ids).sudo()
        employee_dict = {emp.id: emp for emp in real_employees}

        for public in self:
            real = employee_dict.get(public.id)
            if real:
                public.employee_type = real.employee_type
                public.timesheet_cost = real.timesheet_cost or 0.0
                public.profitability_score = real.profitability_score or 0.0
                public.selling_price_per_hour = real.selling_price_per_hour or 0.0
                public.cost_per_hour = real.cost_per_hour or 0.0
                public.total_hours = real.total_hours or 0.0
                public.total_revenue = real.total_revenue or 0.0
                public.total_cost = real.total_cost or 0.0
                public.total_profit = real.total_profit or 0.0
                public.profit_margin = real.profit_margin or 0.0
                public.team_lead_id = real.team_lead_id.id if real.team_lead_id else False
            else:
                public.employee_type = False
                public.timesheet_cost = 0.0
                public.profitability_score = 0.0
                public.selling_price_per_hour = 0.0
                public.cost_per_hour = 0.0
                public.total_hours = 0.0
                public.total_revenue = 0.0
                public.total_cost = 0.0
                public.total_profit = 0.0
                public.profit_margin = 0.0
                public.team_lead_id = False



# class HrEmployeePublic(models.Model):
#     _inherit = 'hr.employee.public'
#
#     employee_type = fields.Selection(
#         selection=[
#             ('technical', 'Technical'),
#             ('non_technical', 'Non-Technical'),
#             ('employee', 'Employee')
#         ],
#         string="Employee Type",
#         readonly=True,
#     )
#
#     timesheet_cost = fields.Float(string="Timesheet Cost", readonly=True)
#
#     # === Remove or comment out the computed fields that are causing errors ===
#     # profitability_score = fields.Float(string="Performance Efficiency (%)", readonly=True)
#     # selling_price_per_hour = fields.Float(string="Selling Price/Hour", readonly=True)
#     # cost_per_hour = fields.Float(string="Cost/Hour", readonly=True)
#     # total_hours = fields.Float(string="Total Hours (Timesheet)", readonly=True)
#     # total_revenue = fields.Float(string="Total Revenue", readonly=True)
#     # total_cost = fields.Float(string="Total Cost", readonly=True)
#     # total_profit = fields.Float(string="Profit", readonly=True)
#     # profit_margin = fields.Float(string="Profit Margin (%)", readonly=True)
#
#     team_lead_id = fields.Many2one(
#         'hr.employee',
#         string="Team Lead",
#         readonly=True,
#     )


class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.onchange('department_id')
    def _onchange_department_ui_update(self):
        if self.department_id:
            self.team_lead_id = self.department_id.team_lead_id
        else:
            self.team_lead_id = False