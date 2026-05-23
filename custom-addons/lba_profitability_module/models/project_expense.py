# -*- coding: utf-8 -*-

from odoo import models, fields, api

import logging
_logger = logging.getLogger(__name__)

#This adds a field to the Expense Module to select Projects, Transport IDs and its Categories associated to a project for a Trip
class ProjectExpense(models.Model):
    _inherit = 'hr.expense'

    project_id = fields.Many2one('project.project', string='Project ID', required=False, store=True)
    transport_trip_id = fields.Many2one('approval.request', string="Transport/Trip Type", domain="[('category_id', '=', category_id)]")
    category_id = fields.Many2one('approval.category', string="Transport Category")