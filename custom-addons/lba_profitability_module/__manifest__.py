{
    'name': "Project Enhancement",

    'summary': """
        This module populates departmental team's details""",

    'description': """
        This module adds the fields for both Departmental Manager and Team lead
    """,

    'author': "LBA ERP TEAM",
    'website': "",

    'category': 'Services/Project Enhancement',
    'version': '0.1',

    'depends': [
        'base', 'project', 'resource', 'hr',
        'project_timesheet_forecast', 'sale_timesheet', 'project_enterprise',
        'hr_timesheet', 'timesheet_grid', 'hr_expense', 'planning',
        'approvals', 'account', 'mail', 'employees_daily_activities_tracking2'
    ],

    'data': [
        'security/project_groups.xml',
        'security/ir.model.access.csv',
        'security/job_rates.xml',
        'data/project_sequence.xml',
        'views/views.xml',
        'views/restricted_views.xml',
        'views/project_job_rate_views.xml',
        'views/project_resource_profitability.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'lba_profitability_module/static/src/css/sticky_header.css',
        ],
    },

    'installable': True,
    'application': False,
    'auto_install': False,

    'demo': [
        'demo/demo.xml',
    ],
}