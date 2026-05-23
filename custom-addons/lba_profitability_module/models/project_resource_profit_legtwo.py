# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProjectResourceProfitLegTwo(models.Model):
    _inherit = 'project.resource.profit'

    @api.model
    def _calc_for_project(self, project):
        rows = super(ProjectResourceProfitLegTwo, self)._calc_for_project(project)

        leg_two_tasks = project.task_ids.filtered(lambda t: t.job_rate_id)
        if not leg_two_tasks:
            return rows

        employee_expected = {}
        for task in leg_two_tasks:
            if task.assigned_employee_ids:
                emp_count = len(task.assigned_employee_ids)
                allocated_hours = (task.planned_hours or 0.0) / emp_count

                for emp in task.assigned_employee_ids:
                    employee_expected[emp.id] = employee_expected.get(emp.id, 0.0) + allocated_hours

        for r in rows:
            emp_id = r.get('employee_id')
            if emp_id in employee_expected:
                r['expected_hours'] = employee_expected[emp_id]

                r['profit'] = r['selling_total'] - r['cost_incurred']
                r['profit_margin'] = (r['profit'] / r['selling_total'] * 100) if r['selling_total'] > 0 else 0.0

        return rows