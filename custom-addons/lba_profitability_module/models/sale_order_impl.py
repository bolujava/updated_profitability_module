from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    project_id = fields.Many2one('project.project', string='Related Project', readonly=True, copy=False)
    project_document_link = fields.Char(
        string='Document Link',
        help="Paste the Microsoft Teams Channel link for project document sharing"
    )

    sales_handover_note = fields.Html(string="Sales Handover Note")

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

    project_attachments = fields.Many2many(
        'ir.attachment',
        'sale_order_project_attachments_rel',
        'sale_order_id',
        'attachment_id',
        string="Project Documents",
        help="Upload documents that will be synced to the project"
    )

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

    def _sync_handover_data(self, project):
        return project._sync_handover_data_from_so(self)

    def action_confirm(self):
        _logger.info("=== START action_confirm for Sales Order(s): %s ===", self.mapped('name'))

        price_map = {
            line: line.price_unit
            for order in self
            for line in order.order_line
            if line.price_unit > 0
        }

        res = super().action_confirm()

        self.flush()
        self.env.cache.invalidate()

        for order in self:
            for line in order.order_line:
                if line in price_map and line.price_unit != price_map[line]:
                    line.sudo().write({
                        'price_unit': price_map[line]
                    })

        for order in self:
            project = order.project_id

            if not project:
                task = self.env['project.task'].sudo().search([
                    ('sale_order_id', '=', order.id)
                ], limit=1)

                if task:
                    project = task.project_id
                else:
                    project = order.order_line.mapped('task_ids.project_id')[:1]

                # Also check for project directly linked to sale order
                if not project:
                    project = self.env['project.project'].sudo().search([
                        ('sale_order_id', '=', order.id)
                    ], limit=1)

            if project:
                if not order.project_id:
                    order.sudo().write({'project_id': project.id})
                    _logger.info(f"✅ Linked Sales Order {order.name} to Project {project.name}")
                    order.refresh()

                order._sync_handover_data(project)

        return res

    def manual_sync_attachments(self):
        """Manual sync button - call this to sync attachments after confirmation"""
        for order in self:
            if not order.project_id:
                raise ValidationError(f"No project linked to Sales Order {order.name}")

            _logger.info(f"Manual sync triggered for SO {order.name}")
            order._sync_handover_data(order.project_id)

            # Post a message to the project chatter
            order.project_id.message_post(
                body=f"📎 Attachments manually synced from Sales Order <a href=# data-oe-model=sale.order data-oe-id={order.id}>{order.name}</a>",
                message_type="notification"
            )

            # Force refresh of attachment count
            order.project_id.invalidate_recordset()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sync Complete',
                'message': f'Attachments synced to project for {len(self)} order(s)',
                'type': 'success',
                'sticky': False,
            }
        }

    def _sync_handover_data_from_so(self, so):
        handover_note = so.sales_handover_note
        document_link = so.project_document_link

        custom_attachments = so.project_attachments
        chatter_attachments = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', so.id)
        ])
        all_attachments = custom_attachments | chatter_attachments

        project_vals = {}

        if handover_note:
            # FIX: Replace instead of combining to avoid duplication
            project_vals.update({
                'sales_handover_note': handover_note,
            })
            _logger.info("✅ Sales Handover Note synced during Project Creation from SO %s", so.name)

        if document_link and hasattr(self, 'document_upload_link'):
            project_vals.update({
                'document_upload_link': document_link,
            })
            _logger.info("✅ Teams link synced from SO")

        if project_vals:
            self.sudo().write(project_vals)

        if all_attachments:
            _logger.info(f"📎 Transferring {len(all_attachments)} attachments from SO {so.name}")
            transferred_count = 0

            for att in all_attachments:
                try:
                    existing = self.env['ir.attachment'].sudo().search([
                        ('res_model', '=', 'project.project'),
                        ('res_id', '=', self.id),
                        ('name', '=', att.name),
                    ], limit=1)

                    if existing:
                        _logger.info(f"  ⏭ Attachment already exists, skipping: {att.name}")
                        continue

                    copied = att.sudo().copy({
                        'res_model': 'project.project',
                        'res_id': self.id,
                        'name': att.name,
                        'description': f"Copied from Sale Order {so.name}",
                        'company_id': self.company_id.id or self.env.company.id,
                    })

                    _logger.info(f"  ✅ Attachment synced: {copied.name}")
                    transferred_count += 1

                except Exception as e:
                    _logger.error(f"  ❌ Failed syncing attachment {att.name}: {str(e)}")

            _logger.info(f"Attachment transfer complete: {transferred_count} synced")

            self._compute_sale_attachments()
            # Force refresh
            self.invalidate_recordset()
        else:
            _logger.info("No attachments to transfer from SO")

    def _transfer_sales_attachments(self, project, attachments):
        if not attachments:
            return

        transferred_count = 0
        skipped_count = 0

        for att in attachments:
            try:
                existing = self.env['ir.attachment'].sudo().search([
                    ('res_model', '=', 'project.project'),
                    ('res_id', '=', project.id),
                    ('name', '=', att.name),
                ], limit=1)

                if existing:
                    _logger.info(f"  ⏭ Attachment already exists, skipping: {att.name}")
                    skipped_count += 1
                    continue

                copied = att.sudo().copy({
                    'res_model': 'project.project',
                    'res_id': project.id,
                    'name': att.name,
                    'description': f"Copied from Sale Order {self.name}",
                    'company_id': project.company_id.id or self.env.company.id,
                })

                _logger.info(f"  ✅ Attachment synced: {copied.name}")
                transferred_count += 1

            except Exception as e:
                _logger.error(f"  ❌ Failed syncing attachment {att.name}: {str(e)}")
                skipped_count += 1

        _logger.info(f"Attachment transfer complete: {transferred_count} synced, {skipped_count} skipped")

        # Post a message to project chatter if any attachments were transferred
        if transferred_count > 0:
            project.message_post(
                body=f"📎 {transferred_count} document(s) synced from Sales Order <a href=# data-oe-model=sale.order data-oe-id={self.id}>{self.name}</a>",
                message_type="notification"
            )
            # Force refresh of smart button count
            project.invalidate_recordset()

    def write(self, vals):
        result = super().write(vals)

        orders_to_sync = self.env['sale.order']

        if 'project_document_link' in vals:
            for order in self:
                if order.project_id:
                    order.project_id.document_upload_link = order.project_document_link
                    _logger.info(f"Synced Teams link from SO {order.name} to Project {order.project_id.name}")
                    orders_to_sync |= order

        if 'sales_handover_note' in vals:
            for order in self:
                if order.project_id and vals.get('sales_handover_note'):
                    # FIX: Replace instead of combining to avoid duplication
                    order.project_id.sudo().write({
                        'sales_handover_note': vals['sales_handover_note'],
                    })
                    _logger.info("Handover note updated via write on SO %s", order.name)
                    orders_to_sync |= order

        if 'project_attachments' in vals:
            for order in self:
                if order.project_id:
                    _logger.info(f"📎 Attachments changed on SO {order.name}, auto-syncing to project...")
                    orders_to_sync |= order

        if 'message_attachment_ids' in vals or 'message_main_attachment_id' in vals:
            for order in self:
                if order.project_id:
                    _logger.info(f"📎 Chatter attachments changed on SO {order.name}, auto-syncing to project...")
                    orders_to_sync |= order

        # Perform the sync for all affected orders
        for order in orders_to_sync:
            if order.project_id:
                order._sync_handover_data(order.project_id)
                _logger.info(f"✅ Auto-sync completed for SO {order.name}")

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
        digits='Product Price',
        # digits=(16,2)
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


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sales_handover_note = fields.Html(
        string="Sales Handover Note",
        readonly=True,
        copy=False
    )

    # Computed field to show sale order attachments on project
    sale_attachment_ids = fields.Many2many(
        'ir.attachment',
        compute='_compute_sale_attachments',
        string="Sales Order Attachments"
    )

    def _compute_sale_attachments(self):
        for project in self:
            if project.sale_order_id:
                so = project.sale_order_id
                custom_attachments = so.project_attachments
                chatter_attachments = self.env['ir.attachment'].search([
                    ('res_model', '=', 'sale.order'),
                    ('res_id', '=', so.id)
                ])
                project.sale_attachment_ids = custom_attachments | chatter_attachments
            else:
                project.sale_attachment_ids = False
        # Force refresh of smart button
        # self.invalidate_recordset()

    @api.constrains('partner_id', 'partner_phone', 'partner_email')
    def _check_customer_contact(self):
        for rec in self:
            if rec.partner_id:
                if not rec.partner_phone:
                    raise ValidationError("Customer phone number is required.")

                if not rec.partner_email:
                    raise ValidationError("Customer email address is required.")