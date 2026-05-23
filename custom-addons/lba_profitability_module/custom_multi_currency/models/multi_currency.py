from odoo import models, fields


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    # Add a flag to identify the additional currencies
    is_additional_currency = fields.Boolean(string="Is Additional Currency")


class Report(models.AbstractModel):
    _inherit = 'account.report'

    def build_result_dict(self, report, query_res_lines):
        rslt = {f'period{i}': 0 for i in range(len(periods))}

        for query_res in query_res_lines:
            for i in range(len(periods)):
                period_key = f'period{i}'
                rslt[period_key] += query_res[period_key]

        # Handle custom second currency computations
        if current_groupby == 'id':
            query_res = query_res_lines[0]
            usd_currency = self.env['res.currency'].search([('is_additional_currency', '=', True)], limit=1)

            rslt.update({
                'amount_currency_2': report.format_value(query_res['amount_currency_2'], currency=usd_currency),
                'currency_2': usd_currency.display_name if usd_currency else None,
            })

        return rslt