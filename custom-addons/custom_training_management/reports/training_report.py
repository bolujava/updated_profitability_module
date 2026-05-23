from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ReportTrainingSummary(models.AbstractModel):
    """Training Summary Report"""
    _name = 'report.custom_training_management.report_training_summary'
    _description = 'Training Summary Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get report values for rendering"""
        docs = self.env['training.attendee'].browse(docids)

        return {
            'doc_ids': docids,
            'doc_model': 'training.attendee',
            'docs': docs,
            'data': data,
            'get_company': self._get_company,
            'get_department_totals': self._get_department_totals,
            'get_payment_summary': self._get_payment_summary,
            'format_currency': self._format_currency,
        }

    def _get_company(self):
        """Get company details"""
        return self.env.company

    def _get_department_totals(self, attendee_ids):
        """Get department totals for summary"""
        departments = {}
        attendees = self.env['training.attendee'].browse(attendee_ids)

        for attendee in attendees:
            dept = attendee.department_id.name or 'No Department'
            if dept not in departments:
                departments[dept] = {
                    'total': 0,
                    'completed': 0,
                    'in_progress': 0,
                    'not_started': 0,
                    'overdue': 0,
                }

            departments[dept]['total'] += 1

            if attendee.state == 'completed':
                departments[dept]['completed'] += 1
            elif attendee.state == 'in_progress':
                departments[dept]['in_progress'] += 1
            else:
                departments[dept]['not_started'] += 1

            if attendee.is_overdue:
                departments[dept]['overdue'] += 1

        return departments

    def _get_payment_summary(self, attendee_ids):
        """Get payment summary for attendees"""
        attendees = self.env['training.attendee'].browse(attendee_ids)

        total_fees = 0
        total_paid = 0
        total_outstanding = 0
        paid_count = 0

        for attendee in attendees:
            if attendee.course_id.is_paid:
                total_fees += attendee.course_id.training_fee
                total_paid += sum(attendee.payment_ids.filtered(lambda p: p.state == 'paid').mapped('amount'))
                if attendee.payment_status == 'paid':
                    paid_count += 1

        total_outstanding = total_fees - total_paid

        return {
            'total_fees': total_fees,
            'total_paid': total_paid,
            'total_outstanding': total_outstanding,
            'paid_count': paid_count,
            'total_count': len(attendees),
        }

    def _format_currency(self, amount, currency=None):
        """Format amount with currency symbol"""
        if not currency:
            currency = self.env.company.currency_id
        return currency.format(amount)


class ReportTrainingCertificate(models.AbstractModel):
    """Training Certificate Report"""
    _name = 'report.custom_training_management.report_training_certificate'
    _description = 'Training Certificate Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get report values for certificate"""
        docs = self.env['training.attendee'].browse(docids)

        # Ensure only completed trainings can have certificates
        for doc in docs:
            if doc.state != 'completed':
                raise UserError(_("Certificate can only be generated for completed trainings!"))

        return {
            'doc_ids': docids,
            'doc_model': 'training.attendee',
            'docs': docs,
            'data': data,
            'get_company': self._get_company,
            'format_date': self._format_date,
        }

    def _get_company(self):
        """Get company details"""
        return self.env.company

    def _format_date(self, date_field):
        """Format date nicely"""
        if date_field:
            return date_field.strftime('%B %d, %Y')
        return ''


class ReportTrainingPaymentReceipt(models.AbstractModel):
    """Payment Receipt Report"""
    _name = 'report.custom_training_management.report_payment_receipt'
    _description = 'Payment Receipt Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get report values for payment receipt"""
        docs = self.env['training.payment'].browse(docids)

        return {
            'doc_ids': docids,
            'doc_model': 'training.payment',
            'docs': docs,
            'data': data,
            'get_company': self._get_company,
            'format_currency': self._format_currency,
        }

    def _get_company(self):
        """Get company details"""
        return self.env.company

    def _format_currency(self, amount, currency=None):
        """Format amount with currency symbol"""
        if not currency:
            currency = self.env.company.currency_id
        return currency.format(amount)


# ===========================================================================
# COMPANY TRAINING REPORT CLASS (MISSING - ADD THIS)
# ===========================================================================

class ReportCompanyTrainingReport(models.AbstractModel):
    """Company-Wide Training Report with Date Range"""
    _name = 'report.custom_training_management.report_company_training'
    _description = 'Company Training Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get report values for company-wide training report"""

        # Get date range from context or data
        date_from = data.get('date_from') if data else False
        date_to = data.get('date_to') if data else False
        report_type = data.get('report_type') if data else 'summary'

        # Build domain
        domain = []
        if date_from:
            domain.append(('date_start', '>=', date_from))
        if date_to:
            domain.append(('date_end', '<=', date_to))

        # Get all attendees within date range
        attendees = self.env['training.attendee'].search(domain, order='date_start desc')

        # Calculate statistics - ALWAYS return a dictionary, even if no records
        stats = self._calculate_statistics(attendees)

        return {
            'doc_ids': docids,
            'doc_model': 'training.attendee',
            'docs': attendees,
            'data': data,
            'stats': stats,
            'date_from': date_from,
            'date_to': date_to,
            'report_type': report_type,  # Pass report type to template
            'get_company': self._get_company,
            'format_currency': self._format_currency,
            'group_by_department': self._group_by_department,
            'group_by_training': self._group_by_training,
        }

    def _get_company(self):
        """Get company details"""
        return self.env.company

    def _format_currency(self, amount, currency=None):
        """Format amount with currency symbol"""
        if not currency:
            currency = self.env.company.currency_id
        return currency.format(amount)

    def _calculate_statistics(self, attendees):
        """Calculate overall statistics - ALWAYS returns a dictionary with all keys"""
        total = len(attendees)
        completed = len(attendees.filtered(lambda a: a.state == 'completed'))
        in_progress = len(attendees.filtered(lambda a: a.state == 'in_progress'))
        not_started = len(attendees.filtered(lambda a: a.state == 'not_started'))
        overdue = len(attendees.filtered(lambda a: a.is_overdue))

        # Payment statistics
        paid_trainings = attendees.filtered(lambda a: a.course_id.is_paid)
        total_fees = sum(paid_trainings.mapped('course_id.training_fee'))
        total_paid = sum(paid_trainings.mapped('payment_ids').filtered(lambda p: p.state == 'paid').mapped('amount'))

        # Return dictionary with ALL keys, even if values are zero
        return {
            'total': total,
            'completed': completed,
            'in_progress': in_progress,
            'not_started': not_started,
            'overdue': overdue,
            'completion_rate': (completed / total * 100) if total > 0 else 0,
            'total_fees': total_fees,
            'total_paid': total_paid,
            'total_outstanding': total_fees - total_paid,
        }

    def _group_by_department(self, attendees):
        """Group attendees by department - ALWAYS returns a dictionary"""
        departments = {}

        if not attendees:
            return departments

        for attendee in attendees:
            dept = attendee.department_id.name or 'No Department'
            if dept not in departments:
                departments[dept] = {
                    'total': 0,
                    'completed': 0,
                    'in_progress': 0,
                    'not_started': 0,
                    'overdue': 0,
                }

            departments[dept]['total'] += 1

            if attendee.state == 'completed':
                departments[dept]['completed'] += 1
            elif attendee.state == 'in_progress':
                departments[dept]['in_progress'] += 1
            else:
                departments[dept]['not_started'] += 1

            if attendee.is_overdue:
                departments[dept]['overdue'] += 1

        # Calculate percentages
        for dept, data in departments.items():
            if data['total'] > 0:
                data['completion_rate'] = (data['completed'] / data['total'] * 100)
            else:
                data['completion_rate'] = 0

        return departments

    def _group_by_training(self, attendees):
        """Group attendees by training course - ALWAYS returns a dictionary"""
        trainings = {}

        if not attendees:
            return trainings

        for attendee in attendees:
            training = attendee.course_id.name
            if training not in trainings:
                trainings[training] = {
                    'total': 0,
                    'completed': 0,
                    'in_progress': 0,
                    'not_started': 0,
                    'overdue': 0,
                    'fee': attendee.course_id.training_fee if attendee.course_id.is_paid else 0,
                }

            trainings[training]['total'] += 1

            if attendee.state == 'completed':
                trainings[training]['completed'] += 1
            elif attendee.state == 'in_progress':
                trainings[training]['in_progress'] += 1
            else:
                trainings[training]['not_started'] += 1

            if attendee.is_overdue:
                trainings[training]['overdue'] += 1

        # Calculate percentages
        for training, data in trainings.items():
            if data['total'] > 0:
                data['completion_rate'] = (data['completed'] / data['total'] * 100)
            else:
                data['completion_rate'] = 0

        return trainings

