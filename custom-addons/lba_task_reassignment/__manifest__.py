# -*- coding: utf-8 -*-
{
    'name': 'LBA Task Reassignment',
    'version': '1.0',
    'category': 'Project',
    'summary': 'Reassign employees to tasks with time transfer',
    'description': """
        Allows reassigning employees to tasks with:
        - Transfer or keep logged time
        - Bulk reassignment
        - Full history tracking
        - Permission control (PMO, PM, Dept Mgr, Team Lead only)
        - Full consistency with lba_profitability_module
    """,
    'author': 'LBA',
    'depends': [
        'lba_profitability_module',
        'hr_timesheet',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizards/task_reassignment_wizard.xml',
        'views/project_task_views.xml',
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'application': False,
}