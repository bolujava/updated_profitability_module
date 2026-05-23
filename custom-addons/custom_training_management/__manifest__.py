{
    'name': 'Training Management',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Complete Training Management Solution',
    'description': """
        Custom Training Management Module built from scratch
        - Training creation and configuration
        - Employee assignment (individual, department, company-wide)
        - Progress tracking with dates
        - Certificate upload
        - Automated notifications and reminders
        - Role-based dashboards and reporting
        - Kanban Board with drag-and-drop functionality
    """,
    'author': 'BOLUWATIFE ADESANYA',
    'depends': ['base', 'hr', 'mail', 'contacts'],
    'data': [
        'security/training_security.xml',
        'security/ir.model.access.csv',
        'data/email_templates.xml',
        'data/scheduled_actions.xml',
        'wizard/assign_training_wizard_views.xml',
        'wizard/company_training_report_wizard_views.xml',
        'views/training_category_views.xml',
        'views/training_course_views.xml',
        'views/training_attendee_views.xml',
        'views/training_dashboard_views.xml',
        'views/training_payment_views.xml',
        'views/training_kanban_views.xml',
        'views/training_menus.xml',
        'reports/training_report_views.xml',
        'reports/training_report_templates.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}