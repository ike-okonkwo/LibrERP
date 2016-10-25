# -*- encoding: utf-8 -*-
##############################################################################
#    
#    Copyright (C) 2013-2016 Didotech SRL
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
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Project Extended',
    'version': '3.11.16.22',
    'category': 'Generic Modules/Projects & Services',
    'description': """Tasks list on a dedicated tab on the project form
""",
    'author': 'Didotech SRL',
    'website': 'http://www.didotech.com',
    'license': 'AGPL-3',
    "depends": [
        'account',
        'project',
        'project_timesheet',
        'task_time_control',
        'res_users_helper_functions'
    ],
    "data": [
        'security/security.xml',
        'views/account_analytic_line.xml',
        'views/project.xml',
        'views/project_task.xml',
        'views/project_view_menu.xml',
        'views/res_partner.xml',
        'views/project_task_work.xml',
    ],
    "active": False,
    "installable": True
}
