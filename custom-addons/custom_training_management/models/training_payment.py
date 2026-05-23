from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class TrainingPayment(models.Model):
    _name = 'training.payment'
    _description = 'Training Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc, id desc'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string="Display Name",
        compute='_compute_display_name',
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    # Relationships
    course_id = fields.Many2one(
        'training.course',
        string="Training Course",
        required=True,
        ondelete='cascade'
    )

    attendee_id = fields.Many2one(
        'training.attendee',
        string="Attendee",
        domain="[('course_id', '=', course_id)]",
        help="Specific employee paying for training (leave blank for company payment)"
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        related='attendee_id.employee_id',
        store=True
    )

    # Payment Details
    amount = fields.Monetary(
        string="Amount",
        currency_field='currency_id',  # This links the amount to the currency
        required=True
    )

    payment_date = fields.Date(
        string="Payment Date",
        required=True,
        default=fields.Date.today
    )

    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
        ('other', 'Other')
    ], string="Payment Method",
        required=True,
        default='bank_transfer'
    )

    payment_reference = fields.Char(
        string="Payment Reference",
        help="Transaction ID, Receipt Number, Cheque Number, etc."
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded')
    ], string="Status",
        default='draft',
        required=True,
        tracking=True
    )

    notes = fields.Text(string="Notes")

    # For payment provider tracking (optional)
    payment_provider = fields.Selection([
        ('manual', 'Manual/Offline'),
        ('bank', 'Bank Transfer'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('flutterwave', 'Flutterwave'),
        ('paystack', 'PayStack')
    ], string="Payment Provider",
        default='manual'
    )

    transaction_id = fields.Char(string="Transaction ID")

    _sql_constraints = [
        ('payment_reference_unique',
         'unique (payment_reference, payment_provider)',
         'Payment reference must be unique per provider!')
    ]

    @api.depends('course_id', 'employee_id', 'payment_reference')
    def _compute_display_name(self):
        for payment in self:
            parts = []
            if payment.course_id:
                parts.append(payment.course_id.name)
            if payment.employee_id:
                parts.append(payment.employee_id.name)
            elif payment.attendee_id:
                parts.append("Company Payment")
            if payment.payment_reference:
                parts.append(f"({payment.payment_reference})")

            payment.display_name = ' - '.join(parts) if parts else 'New Payment'

    @api.constrains('amount')
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(_("Payment amount must be greater than zero!"))

    @api.constrains('payment_date')
    def _check_payment_date(self):
        for payment in self:
            if payment.payment_date > fields.Date.today():
                raise ValidationError(_("Payment date cannot be in the future!"))

    def action_confirm_payment(self):
        """Mark payment as paid"""
        for payment in self:
            if payment.state != 'draft':
                raise UserError(_("Only draft payments can be confirmed!"))

            payment.state = 'paid'

            # Update attendee payment status if linked
            if payment.attendee_id:
                payment.attendee_id._compute_payment_status()

            # Post message in chatter
            payment.message_post(body=_("Payment confirmed. Amount: %s") % payment.amount)

    def action_cancel(self):
        """Cancel the payment"""
        for payment in self:
            if payment.state == 'paid':
                # If cancelling a paid payment, it becomes refunded
                payment.state = 'refunded'
                payment.message_post(body=_("Payment refunded."))
            elif payment.state == 'draft':
                payment.state = 'cancelled'
                payment.message_post(body=_("Payment cancelled."))
            else:
                raise UserError(_("This payment cannot be cancelled in its current state."))

            # Update attendee payment status if linked
            if payment.attendee_id:
                payment.attendee_id._compute_payment_status()

    def action_set_to_draft(self):
        """Reset to draft"""
        for payment in self:
            if payment.state not in ['cancelled', 'refunded']:
                raise UserError(_("Only cancelled or refunded payments can be reset to draft!"))
            payment.state = 'draft'
            payment.message_post(body=_("Payment reset to draft."))