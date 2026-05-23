{
    'name': 'Employee Daily Activity - Validation Extension',
    'version': '1.0',
    'summary': 'Enhanced validation and UI fixes for Daily Activities',
    'category': 'Human Resources',
    'author': 'Your Name',
    'sequence': 200,
    'depends': [
        'hr',
        'hr_timesheet',
        'project',
        'employees_daily_activities_tracking2',
        'lba_profitability_module',
    ],
    'data': [
        'views/activity_view_extension.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

