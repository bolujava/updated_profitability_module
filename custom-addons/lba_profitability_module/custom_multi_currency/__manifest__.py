# -*- coding: utf-8 -*-
{
    "name": "Custom Multi-Currency Reporting",
    "version": "1.0",
    "depends": ["account"],  # Ensure it depends on the 'account' module
    "data": [
        "views/res_currency_views.xml",
        "models/multi_currency.py",
    ],
    "installable": True,
    "application": False,
}
