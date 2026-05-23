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

    employee_type = fields.Selection([
        ('technical', 'Technical'),
        ('non_technical', 'Non-Technical'),
        ('employee', 'Employee')
    ], string="Employee Type", readonly=True)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.onchange('department_id')
    def _onchange_department_ui_update(self):
        if self.department_id:
            self.team_lead_id = self.department_id.team_lead_id
        else:
            self.team_lead_id = False