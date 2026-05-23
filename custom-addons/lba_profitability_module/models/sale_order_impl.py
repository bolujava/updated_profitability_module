from logging import getLogger

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    project_id = fields.Many2one('project.project', string='Related Project')
    project_document_link = fields.Char(
        string='Document Link',
        help="Paste the Microsoft Teams Channel link for project document sharing"
    )
    @api.constrains('project_document_link')
    def _check_project_document_link(self):
        for order in self:
            if order.project_document_link:
                import re
                pattern = r'https?://(?:teams\.microsoft\.com|teams\.live\.com)/.+'
                if not re.match(pattern, order.project_document_link.lower()):
                    raise ValidationError(
                        "Please enter a valid Microsoft Teams URL. "
                        "It should start with 'https://teams.microsoft.com/' or 'https://teams.live.com/'"
                    )
    total_revenue = fields.Float(string="Total Revenue", compute="_compute_profitability", store=True)
    total_cost = fields.Float(string="Total Cost", compute="_compute_profitability", store=True)
    profit = fields.Float(string="Profit", compute="_compute_profitability", store=True)
    profit_margin = fields.Float(string="Profit Margin (%)", compute="_compute_profitability", store=True)

    @api.depends('order_line.price_subtotal', 'order_line.total_cost')
    def _compute_profitability(self):
        for order in self:
            total_revenue = sum(line.price_subtotal for line in order.order_line)
            total_cost = sum(line.total_cost for line in order.order_line)
            profit = total_revenue - total_cost
            profit_margin = (profit / total_revenue * 100) if total_revenue else 0.0

            order.total_revenue = total_revenue
            order.total_cost = total_cost
            order.profit = profit
            order.profit_margin = profit_margin


    def action_confirm(self):
        _logger.info(f"Confirming sale order {self.name}")
        price_map = {line: line.price_unit for line in self.order_line if line.price_unit > 0}

        res = super().action_confirm()

        for order in self:
            for line in order.order_line:
                if line in price_map and line.price_unit != price_map[line]:
                    line.sudo().write({'price_unit': price_map[line]})


        return res


    def write(self, vals):
        result = super().write(vals)

        if 'project_document_link' in vals:
            for order in self:
                if order.project_id:
                    order.project_id.document_upload_link = order.project_document_link
                    _logger.info(f"Synced Teams link from SO {order.name} to Project {order.project_id.name}")

        return result


    def _get_job_rate_for_product(self, product):
        return self.env['project.job.rate'].search([
            ('product_id', '=', product.id)
        ], limit=1)

    project_title = fields.Char(string="Project Title")



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'


    job_rate_id = fields.Many2one(
        'project.job.rate',
        string="Job Rate",
        compute="_compute_job_rate_from_task",
        store=True,
        readonly=False,
        precompute=True
    )

    @api.depends('task_ids')
    def _compute_job_rate_from_task(self):
        for line in self:
            if not line.job_rate_id:
                task = line.task_ids[:1]
                if task:
                    rate = self.env['project.job.rate'].search([
                        ('product_id', '=', line.product_id.id)
                    ], limit=1)
                    line.job_rate_id = rate

    qty_delivered = fields.Float(
        string="Delivered Quantity",
        compute="_compute_delivered_from_tasks",
        store=True,
        digits='Product Unit of Measure'
    )
    task_ids = fields.One2many(
        'project.task',
        'sale_line_id',
        string="Related Tasks"
    )
    @api.depends('task_ids.average_timesheet_hours')
    def _compute_delivered_from_tasks(self):
        for line in self:
            total_delivered = sum(line.task_ids.mapped('average_timesheet_hours'))
            line.qty_delivered = total_delivered
    cost_per_hour = fields.Float(string="Cost/Hour", compute='_compute_cost_per_hour', store=True)
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)
    profit = fields.Float(string='Profit', compute='_compute_profit', store=True)
    price_unit = fields.Float(
        compute='_compute_price_unit_from_job_rate',
        store=True,
        readonly=False,
        default=0.0,
        digits='Product Price'
    )

    @api.depends('job_rate_id', 'product_id')
    def _compute_price_unit_from_job_rate(self):
        for line in self:
            if line.job_rate_id and line.job_rate_id.hourly_rate:
                line.price_unit = line.job_rate_id.hourly_rate

            elif not line.price_unit or line.price_unit == 0.0:
                line.price_unit = line.product_id.list_price or 0.0

    @api.depends('product_id.standard_price')
    def _compute_cost_per_hour(self):
        for line in self:
            line.cost_per_hour = line.product_id.standard_price or 0.0

    @api.depends('qty_delivered', 'cost_per_hour')
    def _compute_total_cost(self):
        for line in self:
            line.total_cost = (line.qty_delivered or 0.0) * (line.cost_per_hour or 0.0)

    @api.depends('price_subtotal', 'total_cost')
    def _compute_profit(self):
        for line in self:
            line.profit = (line.price_subtotal or 0.0) - (line.total_cost or 0.0)

    @api.onchange('job_rate_id')
    def _onchange_job_rate_id(self):
        for line in self:
            if line.job_rate_id:
                rate = line.job_rate_id

                line.product_id = rate.product_id.id if rate.product_id else False

                line.price_unit = rate.hourly_rate or 0.0

                line.cost_per_hour = rate.cost_rate or 0.0

                line.total_cost = line.cost_per_hour * line.product_uom_qty

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        for line in self:
            if line.employee_id and not line.job_rate_id:
                rate = self.env['project.job.rate'].search([
                    ('name', '=', line.employee_id.job_title.name)
                ], limit=1)
                line.job_rate_id = rate.id if rate else False

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue
            job_rate = self.env['project.job.rate'].search([
                ('product_id', '=', line.product_id.id)
            ], limit=1)
            if job_rate:
                line.job_rate_id = job_rate
                line.price_unit = job_rate.hourly_rate or 0.0
                line.cost_per_hour = job_rate.cost_rate or 0.0
                line.total_cost = job_rate.cost_rate * line.product_uom_qty
                _logger.info(f"Matched Job Rate {job_rate.name} for product {line.product_id.name}")
            else:
                line.job_rate_id = False
                if line.product_id.list_price and (not line.price_unit or line.price_unit == 0.0):
                    line.price_unit = line.product_id.list_price
                line.cost_per_hour = line.product_id.standard_price or 0.0
                line.total_cost = line.cost_per_hour * line.product_uom_qty
                _logger.info(f"Standard product detected: {line.product_id.name}. Using list_price.")


