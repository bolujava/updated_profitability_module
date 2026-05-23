from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TrainingCourse(models.Model):
    _name = 'training.course'
    _description = 'Training Course'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # =============================
    # Basic Information
    # =============================
    name = fields.Char(string='Training Title', required=True, tracking=True)
    description = fields.Html(string='Training Description', required=True)

    training_code = fields.Char(
        string="Training Code",
        readonly=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('training.course') or 'New'
    )

    @api.model
    def create(self, vals):
        record = super(TrainingCourse, self).create(vals)

        # Safe training code generation
        try:
            if record.name:
                name_prefix = record.name[:3].upper()
                year = fields.Date.today().strftime('%Y')
                domain = [('training_code', '=like', f'TR/%/{year}/%')]
                last_record = self.search(domain, order='training_code desc', limit=1)
                if last_record and last_record.training_code:
                    last_number = int(last_record.training_code.split('/')[-1])
                    new_number = last_number + 1
                else:
                    new_number = 1
                sequence_number = f"{new_number:03d}"
                record.training_code = f"TR/{name_prefix}/{year}/{sequence_number}"
        except Exception as e:
            _logger.warning("Failed to generate training code safely: %s", e)

        return record

    category_id = fields.Many2one('training.category', string='Training Category', required=True)

    # Training Details
    is_mandatory = fields.Selection([
        ('mandatory', 'Mandatory'),
        ('optional', 'Optional')
    ], string='Mandatory / Optional', required=True, default='optional', tracking=True)

    estimated_duration = fields.Float(string='Estimated Duration (Hours)',
                                      help='Estimated time to complete the training')

    # =====================================
    # RESOURCES, STATUS, PAYMENT, RELATIONSHIPS
    # =====================================
    resource_file = fields.Binary(string='Training Material', attachment=True)
    resource_filename = fields.Char(string='Filename')
    resource_url = fields.Char(string='External Link')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True, required=True)

    completion_rate = fields.Float(string='Completion Rate', compute='_compute_completion_rate', store=True)

    def _compute_completion_rate(self):
        for course in self:
            try:
                if course.assigned_count > 0:
                    course.completion_rate = (course.completed_count / course.assigned_count) * 100
                else:
                    course.completion_rate = 0
            except Exception as e:
                _logger.warning("Failed to compute completion rate for %s: %s", course.name, e)

    # Payment Fields
    is_paid = fields.Boolean(
        string="Paid Training",
        default=False,
        help="Check if this training requires payment"
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )

    training_fee = fields.Monetary(
        string="Training Fee",
        currency_field='currency_id',
        help="Amount to charge for this training",
        default=0.0
    )

    payment_required_before = fields.Selection([
        ('assignment', 'Before Assignment'),
        ('start', 'Before Start Date'),
        ('completion', 'Before Certificate Issuance')
    ], string="Payment Required", default='assignment')

    payment_ids = fields.One2many(
        'training.payment',
        'course_id',
        string="Payments"
    )

    total_paid = fields.Monetary(string="Total Paid", currency_field='currency_id',
                                 compute='_compute_payment_totals', store=True)
    total_outstanding = fields.Monetary(string="Outstanding Balance", currency_field='currency_id',
                                        compute='_compute_payment_totals', store=True)
    payment_count = fields.Integer(string="Payment Count", compute='_compute_payment_totals', store=True)

    @api.depends('payment_ids', 'payment_ids.amount', 'payment_ids.state', 'training_fee',
                 'payment_ids.currency_id', 'currency_id')
    def _compute_payment_totals(self):
        for course in self:
            try:
                confirmed_payments = course.payment_ids.filtered(lambda p: p.state == 'paid')
                total_sum = sum(confirmed_payments.mapped('amount'))
                course.total_paid = total_sum
                course.total_outstanding = course.training_fee - total_sum
                course.payment_count = len(confirmed_payments)
            except Exception as e:
                _logger.warning("Failed to compute payment totals for %s: %s", course.name, e)

    # Relationships
    attendee_ids = fields.One2many('training.attendee', 'course_id', string='Attendees')
    assigned_count = fields.Integer(string='Number Assigned', compute='_compute_assigned_count')
    completed_count = fields.Integer(string='Number Completed', compute='_compute_completed_count')

    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)
    published_date = fields.Datetime(string='Published Date')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Training title already exists!')
    ]

    def _compute_assigned_count(self):
        for course in self:
            try:
                course.assigned_count = len(course.attendee_ids)
            except Exception as e:
                _logger.warning("Failed to compute assigned count for %s: %s", course.name, e)

    def _compute_completed_count(self):
        for course in self:
            try:
                course.completed_count = len(course.attendee_ids.filtered(lambda a: a.state == 'completed'))
            except Exception as e:
                _logger.warning("Failed to compute completed count for %s: %s", course.name, e)

    def action_publish(self):
        self.state = 'published'
        self.published_date = fields.Datetime.now()

    def action_draft(self):
        self.state = 'draft'

    def action_archive(self):
        self.state = 'archived'