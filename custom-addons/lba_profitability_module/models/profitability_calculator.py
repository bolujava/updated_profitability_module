from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ProjectEnhancement(models.Model):
    _inherit = 'project.project'

    delivered_hours = fields.Float(
        string="Delivered Hours",
        compute="_compute_profitability",
        store=True,
        digits=(16, 4),
        help="Actual hours logged via timesheets (qty_delivered from SO lines)"
    )

    total_hours = fields.Float(
        string="Total Hours",
        compute="_compute_profitability",
        store=True,
        help="Total planned hours from SO lines (product_uom_qty)"
    )

    total_planned_hours = fields.Float(
        string="Total Planned Hours (Tasks)",
        compute="_compute_profitability",
        store=True,
        help="Sum of all planned durations from tasks inside this project"
    )

    total_revenue = fields.Float(
        string="Total Selling Price",
        compute="_compute_profitability",
        store=True,
        currency_field="currency_id"
    )

    total_cost = fields.Float(
        string="Total Internal Cost",
        compute="_compute_profitability",
        store=True,
        currency_field="currency_id"
    )

    total_project_cost = fields.Float(
        string="Total Project Cost",
        compute="_compute_profitability",
        store=True,
        currency_field="currency_id",
        help="Total Internal Cost + Total Expenses"
    )

    profit = fields.Float(
        string="Profit",
        compute="_compute_profitability",
        store=True,
        currency_field="currency_id"
    )

    total_profit = fields.Float(
        string="Total Profit",
        compute="_compute_profitability",
        store=True,
        currency_field="currency_id"
    )

    profit_margin = fields.Float(
        string="Profit Margin %",
        compute="_compute_profitability",
        store=True,
        digits=(16, 2)
    )


    @api.depends(
        'task_ids.total_timesheet_hours',
        'task_ids.job_rate_id',
        'task_ids.planned_hours',
        'task_ids.sale_line_id',
        'sale_order_id.order_line.product_uom_qty',
        'sale_order_id.order_line.price_subtotal',  # Focused dependency for contract revenue
        'total_expenses',
    )
    def _compute_profitability(self):
        for project in self:
            _logger.info(f"Computing project profitability from task-linked SO rates: {project.name}")

            total_hours = 0.0
            delivered_hours = 0.0
            total_revenue = 0.0
            total_internal_cost = 0.0
            total_planned_hours = 0.0

            if project.sale_order_id:
                lines = project.sale_order_id.order_line.filtered(lambda l: not l.display_type)
                for line in lines:
                    total_hours += line.product_uom_qty
                    total_revenue += line.price_subtotal


            if project.task_ids:
                planned_hours_list = [task.planned_hours for task in project.task_ids if task.planned_hours]
                if planned_hours_list:
                    total_planned_hours = sum(planned_hours_list) / len(project.task_ids)
                else:
                    total_planned_hours = 0.0

                for task in project.task_ids:
                    active_hours = task.total_timesheet_hours or 0.0
                    delivered_hours += active_hours

                    if task.job_rate_id:
                        hourly_cost = getattr(task.job_rate_id, 'hourly_rate', 0.0)
                        total_internal_cost += active_hours * hourly_cost

                    elif task.sale_line_id:
                        hourly_cost = task.sale_line_id.price_unit
                        total_internal_cost += active_hours * hourly_cost

                    elif project.sale_order_id and project.sale_order_id.order_line:
                        first_line = project.sale_order_id.order_line.filtered(lambda l: not l.display_type)
                        if first_line:
                            hourly_cost = first_line[0].price_unit
                            total_internal_cost += active_hours * hourly_cost

            total_expenses = project.total_expenses or 0.0
            total_project_cost = total_internal_cost + total_expenses
            profit = total_revenue - total_project_cost
            profit_margin = (profit / total_revenue * 100) if total_revenue > 0 else 0.0

            project.total_hours = total_hours
            project.total_planned_hours = total_planned_hours
            project.delivered_hours = delivered_hours
            project.total_revenue = total_revenue
            project.total_cost = total_internal_cost
            project.total_project_cost = total_project_cost
            project.profit = profit
            project.total_profit = profit
            project.profit_margin = profit_margin