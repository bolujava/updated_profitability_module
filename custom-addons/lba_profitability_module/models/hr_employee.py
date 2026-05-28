from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    timesheet_cost = fields.Float(string="Timesheet Cost")

    timesheet_ids = fields.One2many(
        'account.analytic.line',
        'employee_id',
        string="Timesheets"
    )

    # FIXED: Added the required @api.depends decorator below to fix the DB crash
    profitability_score = fields.Float(
        string="Performance Efficiency (%)",
        compute="_compute_profitability_score",
        store=True
    )

    selling_price_per_hour = fields.Float(
        string="Selling Price/Hour",
        compute="_compute_financial_profitability",
        store=True
    )
    cost_per_hour = fields.Float(
        string="Cost/Hour",
        compute="_compute_financial_profitability",
        store=True
    )
    total_hours = fields.Float(
        string="Total Hours (Timesheet)",
        compute="_compute_financial_profitability",
        store=True
    )
    total_revenue = fields.Float(
        string="Total Revenue",
        compute="_compute_financial_profitability",
        store=True
    )
    total_cost = fields.Float(
        string="Total Cost",
        compute="_compute_financial_profitability",
        store=True
    )
    total_profit = fields.Float(
        string="Profit",
        compute="_compute_financial_profitability",
        store=True
    )
    profit_margin = fields.Float(
        string="Profit Margin (%)",
        compute="_compute_financial_profitability",
        store=True
    )

    # ─────────────────────────────────────────────
    # EFFICIENCY COMPUTE METHOD
    # ─────────────────────────────────────────────
    @api.depends('timesheet_ids.unit_amount', 'timesheet_ids.sale_line_id.product_uom_qty')
    def _compute_profitability_score(self):
        for emp in self:
            # OPTIMIZED: Pull from RAM cache instead of executing heavy SQL searches in a loop
            timesheets = emp.timesheet_ids
            total_score = 0.0
            total_sale_lines = set()

            for ts in timesheets:
                sale_line = ts.sale_line_id
                if sale_line and sale_line.product_uom_qty:
                    planned_hours = sale_line.product_uom_qty

                    # OPTIMIZED: Filter in memory
                    total_task_hours = sum(timesheets.filtered(
                        lambda t: t.sale_line_id.id == sale_line.id
                    ).mapped('unit_amount'))

                    total_score += (total_task_hours / planned_hours) * 100
                    total_sale_lines.add(sale_line.id)

            emp.profitability_score = (
                total_score / len(total_sale_lines)
                if total_sale_lines else 0.0
            )

    # ─────────────────────────────────────────────
    # FINANCIAL COMPUTE METHOD
    # ─────────────────────────────────────────────
    @api.depends(
        'timesheet_cost',
        'timesheet_ids.unit_amount',
        'timesheet_ids.task_id.job_rate_id.cost_rate',
        'timesheet_ids.task_id.job_rate_id.selling_rate',
        'timesheet_ids.task_id.job_rate_id.hourly_rate',
        'timesheet_ids.sale_line_id.price_subtotal',
        'timesheet_ids.sale_line_id.product_uom_qty'
    )
    def _compute_financial_profitability(self):
        for emp in self:
            if self.env.context.get('active_model') == 'project.task':
                task_id = self.env.context.get('active_id')
                if task_id:
                    task = self.env['project.task'].browse(task_id)
                    if not task.job_rate_id:
                        continue

            emp.total_hours = 0.0
            emp.selling_price_per_hour = 0.0
            emp.cost_per_hour = 0.0
            emp.total_revenue = 0.0
            emp.total_cost = 0.0
            emp.total_profit = 0.0
            emp.profit_margin = 0.0

            # OPTIMIZED: Use the preloaded field relation instead of doing a search
            timesheets = emp.timesheet_ids

            if not timesheets:
                continue

            total_hours = sum(timesheets.mapped('unit_amount'))
            total_cost = 0.0
            total_revenue = 0.0

            for ts in timesheets:
                hours = ts.unit_amount or 0.0

                if ts.task_id and ts.task_id.job_rate_id:
                    cost_rate = ts.task_id.job_rate_id.cost_rate or 0.0
                else:
                    cost_rate = emp.timesheet_cost or 0.0

                total_cost += hours * cost_rate

                if ts.sale_line_id and ts.sale_line_id.product_uom_qty:
                    so_line = ts.sale_line_id
                    if so_line.product_uom_qty > 0:
                        revenue_rate = so_line.price_subtotal / so_line.product_uom_qty
                        total_revenue += hours * revenue_rate
                elif ts.task_id and ts.task_id.job_rate_id:
                    revenue_rate = ts.task_id.job_rate_id.selling_rate or ts.task_id.job_rate_id.hourly_rate or 0.0
                    total_revenue += hours * revenue_rate

            avg_cost_rate = total_cost / total_hours if total_hours > 0 else 0.0
            avg_revenue_rate = total_revenue / total_hours if total_hours > 0 else 0.0
            total_profit = total_revenue - total_cost
            profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0.0

            emp.total_hours = total_hours
            emp.selling_price_per_hour = avg_revenue_rate
            emp.cost_per_hour = avg_cost_rate
            emp.total_revenue = total_revenue
            emp.total_cost = total_cost
            emp.total_profit = total_profit
            emp.profit_margin = profit_margin