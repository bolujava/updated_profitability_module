# -*- coding: utf-8 -*-
# from odoo import http


# class ProjectEnhancement(http.Controller):
#     @http.route('/project_enhancement/project_enhancement', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/project_enhancement/project_enhancement/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('project_enhancement.listing', {
#             'root': '/project_enhancement/project_enhancement',
#             'objects': http.request.env['project_enhancement.project_enhancement'].search([]),
#         })

#     @http.route('/project_enhancement/project_enhancement/objects/<model("project_enhancement.project_enhancement"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('project_enhancement.object', {
#             'object': obj
#         })
