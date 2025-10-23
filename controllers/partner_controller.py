from datetime import datetime
import logging

from odoo import http, tools, fields
from odoo.http import request, Response
from odoo.exceptions import AccessDenied, UserError, ValidationError
import xmlrpc.client

_logger = logging.getLogger(__name__)


class PartnerController(http.Controller):

    @http.route('/api/tasks', auth='none', methods=['GET'], type='jsonrpc', csrf=False)
    def get_partners(self, **kwargs):
        try:
            # Get the API key from the Authorization header
            api_key = request.httprequest.headers.get('Authorization')
            if not api_key:
                _logger.warning("DOOTIX DEBUG %r", "No API key provided")
                return {'status': 'error', 'message': "No API key provided", 'code': 401}

            user_id = request.env["res.users.apikeys"]._check_credentials(
                scope='rpc', key=api_key
            )

            if not user_id:
                _logger.warning("DOOTIX DEBUG %r", "API key problem")
                return {'status': 'error', 'message': "API key problem", 'code': 403}

            user = request.env['res.users'].sudo().browse(user_id)
            if not user.exists():
                return {'status': 'error', 'message': "Invalid user", 'code': 403}

            # Fetching all tasks
            tasks = request.env['project.task'].with_user(user_id).sudo().search([])

            data = []
            for task in tasks:
                if task.project_id:
                    task_description = tools.html2plaintext(task.description or "")
                    project_description = tools.html2plaintext(
                        task.project_id.description or "") if task.project_id else None

                    partner = task.project_id.partner_id

                    client_object = None
                    if partner:
                        if partner.is_company:
                            company_name = partner.name
                            company_id = partner.id

                            client_object = {
                                'odoo_id': None,
                                'client_name': None,
                                'odoo_company_id': company_id,
                                'company_name': company_name,
                            }
                        else:
                            client_name = partner.name

                            # Retrieve the company associated with the contact
                            company = partner.parent_id

                            client_object = {
                                'odoo_id': partner.id if partner else None,
                                'client_name': client_name,
                                'odoo_company_id': company.id if company else None,
                                'company_name': company.name if company else None,
                            }

                    data.append({
                        'odoo_id': task.id,
                        'name': task.name,
                        'description': task_description,
                        'status': task.state,
                        'allocated_time': getattr(task, 'allocated_hours', 0),

                        # Adding Project Information
                        'project': {
                            'odoo_id': task.project_id.id if task.project_id else None,
                            'name': task.project_id.name if task.project_id else None,
                            'description': project_description,
                        },
                        'client': client_object,
                    })
            return {'status': 'success', 'tasks': data, 'code': 200}
        except AccessDenied as e:
            _logger.warning("DOOTIX DEBUG %r", str(e))
            return {'status': 'error', 'message': str(e), 'code': 403}
        except Exception as e:
            _logger.warning("DOOTIX DEBUG %r", str(e))
            return {'status': 'error', 'message': str(e), 'code': 500}

    @http.route('/api/timesheets', auth='none', methods=['POST'], type='jsonrpc')
    def create_timesheets(self, **kwargs):
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        database = request.env.cr.dbname

        # Extract JSON payload
        data = request.httprequest.get_json()
        timesheets = data.get('timesheets')
        if not timesheets:
            _logger.warning("DOOTIX DEBUG %r", "Missing parameter: timesheets")
            return {'status': 'error', 'message': "Missing parameter: timesheets", 'code': 404}

        try:
            # Get the API key from the Authorization header
            api_key = request.httprequest.headers.get('Authorization')
            if not api_key:
                _logger.warning("DOOTIX DEBUG %r", "No API key provided")
                return {'status': 'error', 'message': "No API key provided", 'code': 401}

            user_id = request.env["res.users.apikeys"]._check_credentials(
                scope='rpc', key=api_key
            )

            if not user_id:
                _logger.warning("DOOTIX DEBUG %r", "API key problem")
                return {'status': 'error', 'message': "API key problem", 'code': 403}

            # Use the Odoo environment directly (no XML-RPC in v19)
            user_env = request.env(user=user_id, su=True)

            created_or_updated_ids = []

            for timesheet in timesheets:
                email = timesheet.get('employee').get('email')
                coclock_instance_id = timesheet.get('coclock_instance_id')
                description = timesheet.get('description')
                duration = timesheet.get('duration') / 60
                project_id = timesheet.get('project_id')
                task_id = timesheet.get('task_id')
                date_obj = datetime.strptime(timesheet.get('start_time'), "%Y-%m-%d")

                # Search for the employee using their email
                employee = user_env['hr.employee'].with_user(user_id).sudo().search(
                    [('work_email', '=', email), ('active', '=', True)], limit=1)

                # Check if employee exists and is active
                if not employee:
                    _logger.warning("DOOTIX DEBUG %r", "No employee found with the given email.")
                    return {'status': 'error', 'message': "No employee found with the given email, please create the employee in Odoo before attempting a synchronisation", 'code': 404}

                account_analytic_line = user_env['account.analytic.line'].search(
                    [('coclock_instance_id', '=', coclock_instance_id)], limit=1
                )

                vals = {
                    'name': description,
                    'employee_id': employee.id,
                    'date': date_obj,
                    'unit_amount': duration,
                    'project_id': project_id,
                    'task_id': task_id,
                    'coclock_instance_id': coclock_instance_id,
                }

                if not account_analytic_line:
                    account_analytic_line = user_env['account.analytic.line'].create(vals)
                else:
                    account_analytic_line.write(vals)

                created_or_updated_ids.append(account_analytic_line.id)

            return {'status': 'success', 'timesheets': created_or_updated_ids, 'code': 200}

        except AccessDenied as e:
            _logger.warning("DOOTIX DEBUG %r", str(e))
            return {'status': 'error', 'message': str(e), 'code': 403}
        except Exception as e:
            _logger.warning("DOOTIX DEBUG %r", str(e))
            return {'status': 'error', 'message': str(e), 'code': 500}
