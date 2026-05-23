# -*- coding: utf-8 -*-

from odoo import models, fields, api

import logging
_logger = logging.getLogger(__name__)


#This adds a field to the Expense Module to select Transport/Trips associated to a project when creating an expense
class ExpenseApproval(models.Model):
    _inherit = 'approval.request'

    project_id = fields.Many2one('project.project', string="Project")
    account_id = fields.Many2one('account.account', string="Account",
    domain=[('deprecated', '=', False)],  # Only active accounts 
    help="Select the account related to this approval request.")