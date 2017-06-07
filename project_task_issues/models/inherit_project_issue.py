# -*- coding: utf-8 -*-
##############################################################################
#    
#    Copyright (C) 2011 Agile Business Group sagl (<http://www.agilebg.com>)
#    Copyright (C) 2011 Domsense srl (<http://www.domsense.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU AfferoGeneral Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import orm, fields
import re


class project_issue(orm.Model):

    _inherit = "project.issue"

    # def name_get(self, cr, uid, ids, context=None):
    #     if not ids:
    #         return []
    #     if isinstance(ids, (int, long)):
    #         ids = [ids]
    #     return [(x['id'], str(x.id)) for x in self.browse(cr, uid, ids, context=context)]

    def on_change_project(self, cr, uid, ids, project_id, email_from, context=None):
        if not project_id:
            return {'value': {}}

        project = self.pool['project.project'].browse(cr, uid, project_id, context=context)

        task_ids = self.pool['project.task'].search(cr, uid, [('project_id', '=', project_id), ('state', 'in', ['open', 'working'])], context=context, limit=1)
        if task_ids and len(task_ids) == 1:
            task_id = task_ids[0]
        else:
            task_id = False
        return {
            'value': {
                'partner_id': project.partner_id and project.partner_id.id,
                'task_id': task_id,
                'analytic_account_id': project.analytic_account_id.id,
            }
        }

    _columns = {
        'work_ids': fields.one2many('project.task.work', 'issue_id', 'Work done'),
        'remaining_hours': fields.related('task_id', 'remaining_hours', type='float', string='Ore rimanenti'),
    }

    def create(self, cr, uid, vals, context):
        if not vals.get('project_id', False):
            if vals.get('email_from'):
                contact_obj = self.pool['res.partner.address.contact']
                project_obj = self.pool['project.project']
                task_obj = self.pool['project.task']
                email_from = re.findall(r'([^ ,<@]+@[^> ,]+)', vals.get('email_from'))
                for email in email_from:
                    contact_ids = contact_obj.search(cr, uid, [('email', '=', email)], context=context)
                    if contact_ids:
                        partner_id = contact_obj.browse(cr, uid, contact_ids, context)[0].partner_id.id
                        project_ids = project_obj.search(cr, uid, [('partner_id', '=', partner_id), ('state', 'in', ['open'])], context=context)
                        if project_ids and len(project_ids) == 1:
                            task_ids = task_obj.search(cr, uid, [('project_id', '=', project_ids[0]), ('state', 'in', ['open', 'working'])],
                                                                        context=context)
                            if task_ids and len(task_ids) == 1:
                                task_id = task_ids[0]
                                user = task_obj.browse(cr, uid, [task_id], context)[0].user_id
                                vals.update({
                                    'partner_id': partner_id,
                                    'project_id': project_ids[0],
                                    'task_id': task_id,
                                    'user_id': user and user.id or False
                                })
                            else:
                                user = project_obj.browse(cr, uid, project_ids, context)[0].user_id
                                vals.update({
                                    'partner_id': partner_id,
                                    'project_id': project_ids[0],
                                    'user_id': user and user.id or False
                                })

        res = super(project_issue, self).create(cr, uid, vals, context)
        return res

    # def case_close(self, cr, uid, ids, *args):
    #     """
    #     @param self: The object pointer
    #     @param cr: the current row, from the database cursor,
    #     @param uid: the current user’s ID for security checks,
    #     @param ids: List of case's Ids
    #     @param *args: Give Tuple Value
    #     """
    #
    #     res = super(project_issue, self).case_close(cr, uid, ids, *args)
    #     # import pdb;pdb.set_trace()
    #     return res


