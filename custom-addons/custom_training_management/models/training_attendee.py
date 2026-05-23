from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date

import logging
_logger = logging.getLogger(__name__)


class TrainingAttendee(models.Model):
    _name = 'training.attendee'
    _description = 'Training Attendee'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'
    _rec_name = 'employee_id'

    # Core Relationships
    course_id = fields.Many2one('training.course', string='Training', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    department_id = fields.Many2one('hr.department', string='Department', related='employee_id.department_id',
                                    store=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True
    )
    # Add this field to your TrainingAttendee class
    training_code = fields.Char(
        string="Training Code",
        related='course_id.training_code',
        store=True,
        readonly=True
    )

    # Assignment Details
    assigned_by = fields.Many2one('res.users', string='Assigned By', default=lambda self: self.env.user, required=True)
    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='Due Date', required=True)
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Priority', default='1')

    # Progress Tracking
    state = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ], string='Status', default='not_started', required=True, tracking=True)


    stage_id = fields.Many2one(
        'training.stage',
        string="Stage",
        default=lambda self: self.env.ref('custom_training_management.training_stage_not_started').id,
        group_expand='_read_group_stage_ids',
        tracking=True,
        index=True,
        copy=False
    )

    # # 1. Define a safe method for the default value
    # def _get_default_stage_id(self):
    #     """Finds the default stage safely to avoid crashes during install/upgrade"""
    #     try:
    #         # First try the XML ID (cleanest method)
    #         return self.env.ref('custom_training_management.training_stage_not_started').id
    #     except (ValueError, AttributeError):
    #         # Fallback: Check if table exists and search by name
    #         self.env.cr.execute("SELECT 1 FROM pg_tables WHERE tablename = 'training_stage'")
    #         if self.env.cr.fetchone():
    #             stage = self.env['training.stage'].search([('name', '=', 'Not Started')], limit=1)
    #             return stage.id if stage else False
    #     return False
    #
    # # 2. Update the field definition
    # stage_id = fields.Many2one(
    #     'training.stage',
    #     string="Stage",
    #     default=_get_default_stage_id,  # Use the function here
    #     group_expand='_read_group_stage_ids',
    #     tracking=True,
    #     index=True,
    #     copy=False
    # )


    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        # This retrieves all stages so they appear as columns even if empty
        return self.env['training.stage'].search([], order=order)


    completion_percentage = fields.Integer(
        string='Completion %',
        default=0,
        tracking=True
    )

    notes = fields.Text(string='Comments/Notes')
    date_completed = fields.Date(string='Completion Date')

    certificate_file = fields.Binary(string='Certificate', attachment=True)
    certificate_filename = fields.Char(string='Certificate Filename')
    certificate_uploaded = fields.Boolean(string='Certificate Uploaded', compute='_compute_certificate_uploaded',
                                          store=True)
    is_overdue = fields.Boolean(string='Overdue', compute='_compute_is_overdue', store=True)
    overdue_days = fields.Integer(string='Overdue Days', compute='_compute_overdue_days', store=True)

    course_description = fields.Html(string='Course Description', related='course_id.description', readonly=True)

    # Assignment Type (for reporting)
    assignment_type = fields.Selection([
        ('individual', 'Individual'),
        ('department', 'Department'),
        ('company', 'Company Wide')
    ], string='Assignment Type', default='individual')

    # ===== NEW PAYMENT FIELDS =====
    payment_status = fields.Selection([
        ('pending', 'Pending Payment'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('waived', 'Payment Waived')
    ], string="Payment Status",
        compute='_compute_payment_status',
        store=True,
        tracking=True
    )

    payment_ids = fields.One2many(
        'training.payment',
        'attendee_id',
        string="Payments"
    )

    can_access_training = fields.Boolean(
        string="Can Access Training",
        compute='_compute_can_access_training',
        store=True
    )
    # ===== END NEW PAYMENT FIELDS =====

    # ===== KANBAN BOARD ENHANCEMENTS =====
    progress_status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue')
    ],
        string="Progress Status",
        compute='_compute_progress_status',
        inverse='_inverse_progress_status',
        store=True,
        tracking=True
    )

    def _inverse_progress_status(self):
        for record in self:

            if record.progress_status == 'not_started':
                record.state = 'not_started'
                record.completion_percentage = 0

            elif record.progress_status == 'in_progress':
                record.state = 'in_progress'
                if record.completion_percentage == 0:
                    record.completion_percentage = 50

            elif record.progress_status == 'completed':
                record.state = 'completed'
                record.completion_percentage = 100
                record.date_completed = fields.Date.today()

            elif record.progress_status == 'overdue':
                if record.state != 'completed':
                    record.state = 'in_progress'

    kanban_color = fields.Integer(string='Kanban Color', compute='_compute_kanban_color', store=True)

    @api.onchange('stage_id')
    def _onchange_stage_id(self):
        """Automatically update the technical 'state' when the Kanban stage changes"""
        if self.stage_id:
            # Match the stage name to your selection state
            if self.stage_id.name == 'Not Started':
                self.state = 'not_started'
                self.completion_percentage = 0
                self.date_completed = False
            elif self.stage_id.name == 'In Progress':
                self.state = 'in_progress'
                if self.completion_percentage == 0:
                    self.completion_percentage = 50
            elif self.stage_id.name == 'Completed' and self.state != 'completed':
                # Just update fields, don't call action_mark_completed()
                self.state = 'completed'
                self.completion_percentage = 100
                self.date_completed = fields.Date.today()
                # Email will be sent when the record is actually saved
            elif self.stage_id.name == 'Overdue':
                if self.state != 'completed':
                    self.state = 'in_progress'
                    self.is_overdue = True
    # ===== END KANBAN BOARD ENHANCEMENTS =====

    # SQL Constraints
    _sql_constraints = [
        ('unique_employee_course', 'unique (employee_id, course_id)',
         'This training is already assigned to this employee!')
    ]

    @api.depends('certificate_file')
    def _compute_certificate_uploaded(self):
        for record in self:
            record.certificate_uploaded = bool(record.certificate_file)

    @api.depends('date_end', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for record in self:
            record.is_overdue = record.date_end and record.date_end < today and record.state != 'completed'

    @api.depends('date_end', 'is_overdue')
    def _compute_overdue_days(self):
        today = fields.Date.today()
        for record in self:
            if record.is_overdue and record.date_end:
                record.overdue_days = (today - record.date_end).days
            else:
                record.overdue_days = 0

    # ===== KANBAN COMPUTE METHODS =====
    @api.depends('completion_percentage', 'state', 'is_overdue')
    def _compute_progress_status(self):
        """Compute progress status for Kanban board"""
        for record in self:
            if record.is_overdue:
                record.progress_status = 'overdue'
            elif record.completion_percentage >= 100:
                record.progress_status = 'completed'
            elif record.completion_percentage > 0:
                record.progress_status = 'in_progress'
            else:
                record.progress_status = 'not_started'

    @api.depends('priority', 'is_overdue')
    def _compute_kanban_color(self):
        """Compute color for Kanban cards based on priority/status"""
        for record in self:
            if record.is_overdue:
                record.kanban_color = 1  # Red for overdue
            elif record.priority == '3':
                record.kanban_color = 2  # Orange for urgent
            elif record.priority == '2':
                record.kanban_color = 3  # Yellow for high
            elif record.priority == '1':
                record.kanban_color = 4  # Blue for medium
            else:
                record.kanban_color = 5  # Gray for low

    @api.onchange('completion_percentage')
    def _onchange_completion_percentage(self):
        """Trigger when user manually inputs progress percentage"""
        for record in self:
            # Validate percentage
            if record.completion_percentage < 0:
                record.completion_percentage = 0
                return {'warning': {'title': 'Warning', 'message': 'Percentage cannot be negative'}}
            if record.completion_percentage > 100:
                record.completion_percentage = 100
                return {'warning': {'title': 'Warning', 'message': 'Percentage cannot exceed 100'}}

            # Update state based on percentage
            if record.completion_percentage >= 100:
                record.state = 'completed'
                record.date_completed = fields.Date.today()
            elif record.completion_percentage > 0:
                record.state = 'in_progress'
                record.date_completed = False
            else:
                record.state = 'not_started'
                record.date_completed = False


    # ===== END KANBAN COMPUTE METHODS =====

    # ===== NEW PAYMENT COMPUTE METHODS =====
    @api.depends('course_id.is_paid', 'payment_ids.amount', 'payment_ids.state')
    def _compute_payment_status(self):
        for attendee in self:
            if not attendee.course_id.is_paid:
                attendee.payment_status = False
                continue

            paid_amount = sum(attendee.payment_ids.filtered(lambda p: p.state == 'paid').mapped('amount'))
            fee = attendee.course_id.training_fee

            if paid_amount >= fee:
                attendee.payment_status = 'paid'
            elif paid_amount > 0:
                attendee.payment_status = 'partial'
            else:
                attendee.payment_status = 'pending'

    @api.depends('course_id.is_paid', 'payment_status', 'course_id.payment_required_before', 'state')
    def _compute_can_access_training(self):
        for attendee in self:
            # Default to True
            attendee.can_access_training = True

            # If training is not paid, always accessible
            if not attendee.course_id.is_paid:
                continue

            # Check based on payment requirement timing
            if attendee.course_id.payment_required_before == 'assignment':
                # Must be paid before being assigned
                if attendee.payment_status not in ['paid', 'waived']:
                    attendee.can_access_training = False

            elif attendee.course_id.payment_required_before == 'start':
                # Can access until they try to start
                # We'll check in action_start_training
                pass

            elif attendee.course_id.payment_required_before == 'completion':
                # Can access until they try to complete
                # We'll check in action_mark_completed
                pass

    # ===== END NEW PAYMENT COMPUTE METHODS =====

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end:
                if record.date_end < record.date_start:
                    raise ValidationError('Due Date cannot be earlier than Start Date.')

    @api.constrains('completion_percentage')
    def _check_percentage(self):
        for record in self:
            if record.completion_percentage and (
                    record.completion_percentage < 0 or record.completion_percentage > 100):
                raise ValidationError('Completion percentage must be between 0 and 100.')

    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'completed' and not self.date_completed:
            self.date_completed = fields.Date.today()
        elif self.state != 'completed':
            self.date_completed = False



    def action_start_training(self):
        # ===== PAYMENT CHECK ADDED =====
        for attendee in self:
            if attendee.course_id.is_paid and attendee.course_id.payment_required_before == 'start':
                if attendee.payment_status not in ['paid', 'waived']:
                    raise ValidationError(_(
                        "Payment required before starting this training!\n"
                        "Training Fee: %s\n"
                        "Amount Paid: %s\n"
                        "Outstanding: %s"
                    ) % (
                        attendee.course_id.training_fee,
                        sum(attendee.payment_ids.filtered(lambda p: p.state == 'paid').mapped('amount')),
                        attendee.course_id.training_fee - sum(attendee.payment_ids.filtered(lambda p: p.state == 'paid').mapped('amount'))
                    ))
        # ===== END PAYMENT CHECK =====
        self.state = 'in_progress'
        self.completion_percentage = 10

    def action_mark_completed(self):
        # ===== PAYMENT CHECK ADDED =====
        for attendee in self:
            if attendee.course_id.is_paid and attendee.course_id.payment_required_before == 'completion':
                if attendee.payment_status not in ['paid', 'waived']:
                    raise ValidationError(_(
                        "Payment required before completing this training!\n"
                        "Training Fee: %s\n"
                        "Amount Paid: %s\n"
                        "Outstanding: %s"
                    ) % (
                        attendee.course_id.training_fee,
                        sum(attendee.payment_ids.filtered(lambda p: p.state == 'paid').mapped('amount')),
                        attendee.course_id.training_fee - sum(attendee.payment_ids.filtered(lambda p: p.state == 'paid').mapped('amount'))
                    ))
        # ===== END PAYMENT CHECK =====
        for record in self:
            record.write({
                'state': 'completed',
                'completion_percentage': 100,
                'date_completed': fields.Date.today()
            })
            record._send_completion_notification()

        return True

    def _send_completion_notification(self):
        """Send completion email safely"""
        template = self.env.ref(
            'custom_training_management.email_template_training_completed',
            raise_if_not_found=False
        )

        if not template:
            return False

        for record in self:
            template.send_mail(
                record.id,
                force_send=True,
                raise_exception=False
            )

        return True

    def action_reset_to_not_started(self):
        self.state = 'not_started'
        self.completion_percentage = 0
        self.date_completed = False

    # def send_weekly_reminders(self):
    #     """Send weekly reminder emails to employees with incomplete trainings (Section 8.2)"""
    #     today = fields.Date.today()
    #     attendees_to_remind = self.search([
    #         ('state', '!=', 'completed'),
    #         ('date_end', '>=', today),
    #         ('employee_id', '!=', False)
    #     ])
    #
    #     reminder_template = self.env.ref('custom_training_management.email_template_weekly_reminder',
    #                                      raise_if_not_found=False)
    #
    #     if not reminder_template:
    #         return
    #
    #     for attendee in attendees_to_remind:
    #         # Send individual reminder for each pending training
    #         reminder_template.send_mail(attendee.id, force_send=True)
    #
    #     # Optional: Log the action
    #     self.env['ir.logging'].create({
    #         'name': 'Weekly Training Reminders',
    #         'type': 'server',
    #         'level': 'info',
    #         'message': f'Sent {len(attendees_to_remind)} weekly reminder emails',
    #         'path': 'training.attendee.send_weekly_reminders',
    #         'func': 'send_weekly_reminders',
    #         'line': '0',
    #     })
    #
    #     return True
    def send_weekly_reminders(self):
        """Send weekly reminder emails to employees with incomplete trainings"""

        today = fields.Date.today()

        attendees_to_remind = self.sudo().search([
            ('state', '!=', 'completed'),
            ('date_end', '>=', today),
            ('employee_id', '!=', False),
        ])

        if not attendees_to_remind:
            return True

        template = self.env.ref(
            'custom_training_management.email_template_weekly_reminder',
            raise_if_not_found=False
        )

        if not template:
            _logger.warning("Weekly reminder template not found")
            return True

        sent_count = 0

        for attendee in attendees_to_remind:

            # Skip if no partner/email
            partner = attendee.employee_id.partner_id
            if not partner or not partner.email:
                continue

            try:
                attendee.flush()
                self.env.cr.commit()
                fresh = attendee.sudo().browse(attendee.id)

                template.sudo().send_mail(
                    fresh.id,
                    force_send=True,
                    raise_exception=False,
                    email_values={
                        'recipient_ids': [(6, 0, [partner.id])],
                        'email_from': fresh.company_id.email or self.env.user.email
                    }
                )

                sent_count += 1

            except Exception as e:
                _logger.exception(
                    "Weekly reminder failed for attendee %s: %s",
                    attendee.id, str(e)
                )

        _logger.info(
            "Weekly Training Reminders: Sent %s emails",
            sent_count
        )

        return True


    def action_download_certificate(self):
        """Allows Managers to quickly download the file from the form view"""
        self.ensure_one()
        if not self.certificate_file:
            return False
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=training.attendee&id={self.id}&field=certificate_file&download=true&filename={self.certificate_filename}',
            'target': 'new',
        }

    def write(self, vals):
        # Track if we're already in a recursive call
        if self.env.context.get('skip_recursion'):
            return super(TrainingAttendee, self).write(vals)

        # Track if completion percentage changed
        percentage_changed = 'completion_percentage' in vals
        old_percentages = {}

        if percentage_changed:
            # Store old percentages before write
            for record in self:
                old_percentages[record.id] = {
                    'percentage': record.completion_percentage,
                    'state': record.state,
                    'was_completed': record.state == 'completed'
                }

        # Detect stage change BEFORE write
        stage_changed = 'stage_id' in vals

        # Perform the actual write with recursion prevention
        res = super(TrainingAttendee, self.with_context(skip_recursion=True)).write(vals)

        # Apply logic AFTER write so record.stage_id is correct
        if stage_changed:
            for record in self:
                if record.stage_id:
                    if record.stage_id.name == 'Not Started':
                        # Use sudo to avoid recursion and direct assignment
                        super(TrainingAttendee, record).with_context(skip_recursion=True).write({
                            'state': 'not_started',
                            'completion_percentage': 0
                        })
                    elif record.stage_id.name == 'In Progress':
                        vals_to_write = {'state': 'in_progress'}
                        if record.completion_percentage == 0:
                            vals_to_write['completion_percentage'] = 50
                        super(TrainingAttendee, record).with_context(skip_recursion=True).write(vals_to_write)
                    elif record.stage_id.name == 'Completed':
                        super(TrainingAttendee, record).with_context(skip_recursion=True).write({
                            'state': 'completed',
                            'completion_percentage': 100,
                            'date_completed': fields.Date.today()
                        })
                    elif record.stage_id.name == 'Overdue':
                        if record.state != 'completed':
                            super(TrainingAttendee, record).with_context(skip_recursion=True).write({
                                'state': 'in_progress',
                                'is_overdue': True
                            })

        # Handle manual percentage changes - update stage accordingly
        if percentage_changed:
            for record in self:
                # Update stage based on new percentage (with recursion prevention)
                record.with_context(skip_recursion=True)._update_stage_from_progress()

                # Handle completion notification
                old_data = old_percentages.get(record.id, {})
                old_was_completed = old_data.get('was_completed', False)
                if record.completion_percentage >= 100 and not old_was_completed:
                    record._send_completion_notification()

        # Certificate notification logic
        if 'certificate_file' in vals and vals['certificate_file']:
            for record in self:
                record._notify_manager_certificate_upload()

        return res

    def _notify_manager_certificate_upload(self):
        """Sends an email to the HR Manager when a certificate is uploaded"""
        template = self.env.ref('custom_training_management.email_template_certificate_uploaded_manager',
                                raise_if_not_found=False)
        if template:
            # You can define a specific manager email or send to the 'assigned_by' user
            template.send_mail(self.id, force_send=True)

    # ===== KANBAN ACTION METHODS =====
    def action_update_progress_from_kanban(self, new_status):
        """Update progress when card is dragged to new column"""
        self.ensure_one()

        status_map = {
            'not_started': 0,
            'in_progress': 50,  # Default to 50% when dragged to in progress
            'completed': 100,
            'overdue': self.completion_percentage,  # Keep same percentage
        }

        if new_status not in status_map:
            return False

        new_percentage = status_map[new_status]

        # Only update if different
        if self.completion_percentage != new_percentage or self.state != new_status:
            vals = {}
            if new_status == 'completed':
                vals.update({
                    'completion_percentage': 100,
                    'state': 'completed',
                    'date_completed': fields.Date.today()
                })
            elif new_status == 'overdue':
                # Set overdue without sending completion email
                vals.update({
                    'state': 'in_progress',
                    'is_overdue': True
                })
            elif new_status == 'in_progress':
                vals.update({
                    'completion_percentage': max(new_percentage, self.completion_percentage),
                    'state': 'in_progress'
                })
            elif new_status == 'not_started':
                vals.update({
                    'completion_percentage': 0,
                    'state': 'not_started'
                })

            self.write(vals)

            # Only send completion notification when truly completed
            if new_status == 'completed':
                self._send_completion_notification()

        return True

    def get_kanban_columns(self):
        """Return kanban columns configuration"""
        return [
            {'id': 'not_started', 'name': 'Not Started', 'status': 'not_started',
             'limit': 10, 'color': '#6c757d'},
            {'id': 'in_progress', 'name': 'In Progress', 'status': 'in_progress',
             'limit': 10, 'color': '#007bff'},
            {'id': 'completed', 'name': 'Completed', 'status': 'completed',
             'limit': 10, 'color': '#28a745'},
            {'id': 'overdue', 'name': 'Overdue', 'status': 'overdue',
             'limit': 10, 'color': '#dc3545'},
        ]

    @api.model
    def _cron_mark_overdue_trainings(self):
        """Cron job: mark trainings as overdue if past end date."""
        today = fields.Date.today()
        overdue_attendees = self.search([
            ('state', '!=', 'completed'),
            ('date_end', '<', today)
        ])
        if overdue_attendees:
            overdue_attendees.action_mark_overdue()

    # def action_mark_overdue(self):
    #     """Mark training as overdue and notify employee, manager + People Services group"""
    #     today = fields.Date.today()
    #     overdue_attendees = self.filtered(lambda r: r.state != 'completed' and r.date_end and r.date_end < today)
    #     if not overdue_attendees:
    #         return True
    #
    #     # Update state and overdue flag
    #     overdue_attendees.write({
    #         'state': 'in_progress',  # Keep in progress
    #         'is_overdue': True
    #     })
    #
    #     # Get People Services group
    #     people_service_group = self.env.ref('custom_training_management.group_training_admin', raise_if_not_found=False)
    #
    #     for attendee in overdue_attendees:
    #         # Prepare recipients: employee + manager + People Services
    #         partner_ids = [attendee.employee_id.partner_id.id]  # employee always recipient
    #
    #         # Add employee's manager if exists
    #         if attendee.employee_id.parent_id and attendee.employee_id.parent_id.partner_id:
    #             partner_ids.append(attendee.employee_id.parent_id.partner_id.id)
    #
    #         # Add all People Services users
    #         if people_service_group:
    #             partner_ids.extend([user.partner_id.id for user in people_service_group.users if user.partner_id])
    #
    #         # Remove duplicates just in case
    #         partner_ids = list(set(partner_ids))
    #
    #         # Send overdue email template
    #         template = self.env.ref('custom_training_management.email_template_training_overdue',
    #                                 raise_if_not_found=False)
    #         if template:
    #             template.send_mail(
    #                 attendee.id,
    #                 force_send=True,
    #                 raise_exception=False,
    #                 email_values={'recipient_ids': [(6, 0, partner_ids)]}
    #             )
    #
    #     return True
    def action_mark_overdue(self):
        """Mark training as overdue and notify employee, manager + People Services group"""

        today = fields.Date.today()

        overdue_attendees = self.filtered(
            lambda r: r.state != 'completed' and r.date_end and r.date_end < today
        )

        if not overdue_attendees:
            return True

        overdue_attendees.write({
            'state': 'in_progress',
            'is_overdue': True
        })

        people_service_group = self.env.ref(
            'custom_training_management.group_training_admin',
            raise_if_not_found=False
        )

        template = self.env.ref(
            'custom_training_management.email_template_training_overdue',
            raise_if_not_found=False
        )

        if not template:
            return True

        for attendee in overdue_attendees:

            partner_ids = []

            # Employee
            if attendee.employee_id.partner_id:
                partner_ids.append(attendee.employee_id.partner_id.id)

            # Manager
            manager = attendee.employee_id.parent_id
            if manager and manager.partner_id:
                partner_ids.append(manager.partner_id.id)

            # People Services
            if people_service_group:
                for user in people_service_group.users:
                    if user.partner_id:
                        partner_ids.append(user.partner_id.id)

            # Remove duplicates
            partner_ids = list(set(partner_ids))

            if not partner_ids:
                continue

            try:
                # Ensure record is fresh
                attendee.flush()
                self.env.cr.commit()
                fresh = attendee.sudo().browse(attendee.id)

                template.sudo().send_mail(
                    fresh.id,
                    force_send=True,
                    raise_exception=False,
                    email_values={
                        'recipient_ids': [(6, 0, partner_ids)],
                        'email_from': fresh.company_id.email or self.env.user.email
                    }
                )

            except Exception as e:
                _logger.exception(
                    "Failed to send overdue notification for attendee %s: %s",
                    attendee.id, str(e)
                )

        return True

    def action_apply_progress(self):
        """Apply manual progress input and sync with Kanban"""
        self.ensure_one()

        # Validate percentage
        if self.completion_percentage < 0 or self.completion_percentage > 100:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Invalid Value'),
                    'message': _('Progress must be between 0 and 100'),
                    'sticky': False,
                    'type': 'danger',
                }
            }

        # Update state based on percentage (your existing logic will handle this)
        # The write method will trigger all necessary updates

        # Force stage update based on progress
        self._update_stage_from_progress()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Progress Updated'),
                'message': _('Training progress updated to %s%%') % self.completion_percentage,
                'sticky': False,
                'type': 'success',
            }
        }

    # def _update_stage_from_progress(self):
    #     """Update Kanban stage based on progress percentage"""
    #     stage_model = self.env['training.stage']
    #
    #     if self.completion_percentage >= 100:
    #         stage = stage_model.search([('name', '=', 'Completed')], limit=1)
    #         if stage:
    #             self.stage_id = stage.id
    #     elif self.completion_percentage > 0:
    #         stage = stage_model.search([('name', '=', 'In Progress')], limit=1)
    #         if stage:
    #             self.stage_id = stage.id
    #     else:
    #         stage = stage_model.search([('name', '=', 'Not Started')], limit=1)
    #         if stage:
    #             self.stage_id = stage.id
    def _update_stage_from_progress(self):
        """Update Kanban stage based on progress percentage"""
        stage_model = self.env['training.stage']

        # Don't run if we're already in a recursive call
        if self.env.context.get('skip_recursion'):
            return

        if self.completion_percentage >= 100:
            target_stage = stage_model.search([('name', '=', 'Completed')], limit=1)
        elif self.completion_percentage > 0:
            target_stage = stage_model.search([('name', '=', 'In Progress')], limit=1)
        else:
            target_stage = stage_model.search([('name', '=', 'Not Started')], limit=1)

        if target_stage and self.stage_id != target_stage:
            self.with_context(skip_recursion=True).write({'stage_id': target_stage.id})


class TrainingStage(models.Model):
    _name = 'training.stage'
    _description = 'Training Stage'
    _order = 'sequence'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=1)
    fold = fields.Boolean("Folded in Kanban")
