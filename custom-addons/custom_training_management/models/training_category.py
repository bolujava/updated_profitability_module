from odoo import models, fields, api

class TrainingCategory(models.Model):
    _name = 'training.category'
    _description = 'Training Category'
    _order = 'name'

    name = fields.Char(string='Category Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
    course_count = fields.Integer(string='Number of Courses', compute='_compute_course_count')

    def _compute_course_count(self):
        for category in self:
            category.course_count = self.env['training.course'].search_count([('category_id', '=', category.id)])