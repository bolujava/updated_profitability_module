# -*- coding: utf-8 -*-

from odoo import models, fields, api

import logging
_logger = logging.getLogger(__name__)

#This integrates the account.move model to the approval module
class AccountMove(models.Model):
    _inherit = 'account.move'

    approval_request_id = fields.Many2one('approval.request', string="Approval Request",
    help="Approval request linked to this journal entry.")