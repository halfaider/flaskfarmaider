import json
import logging
import urllib.parse
import traceback
import re

import flask
import flask_login
from flask import request

from framework.init_main import Framework
from framework.scheduler import Job as FrameworkJob
from plugin.create_plugin import create_plugin_instance
from plugin.create_plugin import PluginBase
from plugin.logic_module_base import PluginModuleBase, PluginPageBase
from plugin.model_base import ModelBase
from plugin.route import default_route_socketio_module
from system.setup import P as SYSTEM_PLUGIN
from support import AlchemyEncoder

from .constants import OPTS
from .util import get_client_ip, get_rotating_file_logger

OPTS['filepath'] = __file__
PLUGIN = P = create_plugin_instance(OPTS)
LOGGER = PLUGIN.logger
CONFIG = PLUGIN.ModelSetting
FRAMEWORK = F = Framework.get_instance()


def celery_is_active() -> bool:
    try:
        return True if FRAMEWORK.celery.control.inspect().stats() else False
    except:
        return False


system_route = SYSTEM_PLUGIN.logic.get_module('route')
system_route_process_command = system_route.process_command
def set_login_log(enable: bool = True) -> None:
    if enable:
        system_route.process_command = commad_process_route_system
    else:
        system_route.process_command = system_route_process_command


def commad_process_route_system(command: str, arg1: str | None, arg2: str | None, arg3: str | None, request: flask.Request) -> flask.Response:
    '''alternative of system.route.process_command()'''
    if command == 'login':
        username = arg1
        password = arg2
        remember = (arg3 == 'true')
        client_info = f"user={username} ip={get_client_ip(request)}"
        failed_msg = f'로그인 실패: {client_info}'
        if username not in FRAMEWORK.users:
            SYSTEM_PLUGIN.logger.warning(failed_msg)
            return flask.jsonify('no_id')
        elif not FRAMEWORK.users[username].can_login(password):
            SYSTEM_PLUGIN.logger.warning(failed_msg)
            return flask.jsonify('wrong_password')
        else:
            SYSTEM_PLUGIN.logger.info(f'로그인 성공: {client_info}')
            FRAMEWORK.users[username].authenticated = True
            flask_login.login_user(FRAMEWORK.users[username], remember=remember)
            return flask.jsonify('redirect')


def setting_get_json(key: str) -> dict | list:
    try:
        return json.loads(CONFIG.get(key))
    except:
        LOGGER.error(traceback.format_exc())
        LOGGER.error(f'Invalid JSON: {CONFIG.get(key)}')
        if type(CONFIG.get(key)) is str:
            return [CONFIG.get(key)]
        else:
            return {}


def setting_set_json(key: str, value: dict | list) -> bool:
    try:
        CONFIG.set(key, json.dumps(value))
        return True
    except Exception as e:
        LOGGER.error(traceback.format_exc())
        LOGGER.eroror(f'Invalid JSON: {value}')
        return False


def setting_get_boolean(key: str) -> bool:
    value = CONFIG.get(key) or 'false'
    match value.lower():
        case 'true' | 'on' | 'yes':
            value = True
        case 'false' | 'off' | 'no':
            value = False
        case _:
            LOGGER.error(f'Could not determine a boolean type: {value}')
            value = False
    return value


CONFIG.get_json = setting_get_json
CONFIG.set_json = setting_set_json
CONFIG.get_boolean = setting_get_boolean


@FRAMEWORK.app.after_request
def after_request(response: flask.Response) -> flask.Response:
    if CONFIG.get_boolean('setting_logging_access'):
        request = flask.request
        apikey = SYSTEM_PLUGIN.ModelSetting.get('apikey')
        form = urllib.parse.urlencode(request.form, doseq=True)
        namespace = {
            'remote': get_client_ip(request),
            'method': request.method,
            'scheme': request.scheme,
            'path': request.full_path.replace(apikey, '<REDACTED>') if apikey else request.full_path,
            'status': response.status_code,
            'agent': request.user_agent,
            'length': response.content_length,
            'form': form.replace(apikey, '<REDACTED>') if apikey else form,
            'headers': request.headers,
            'hostname': urllib.parse.urlparse(request.base_url).hostname,
        }
        log_format = CONFIG.get('setting_logging_access_format') or '{remote} {method} "{path}" {status}'
        if regexes := CONFIG.get('setting_logging_access_regex'):
            filters = [re.compile(line) for line in regexes.splitlines() if line]
        else:
            filters = []
        try:
            log_message = log_format.format(**namespace)
            for filter in filters:
                if filter.search(log_message):
                    break
            else:
                CONFIG.access_logger.info(log_message)
        except:
            LOGGER.exception(f'엑세스 로그 형식 확인: {log_format}')
    return response


file = CONFIG.get('setting_logging_access_file') or f"{FRAMEWORK.config.get('path_data', '/data')}/log/access.log"
CONFIG.access_logger = get_rotating_file_logger(file, level=logging.INFO)


from .presenters import Setting
from .presenters import Schedule
from .presenters import Manual
from .presenters import Tool

PLUGIN.set_module_list([Setting, Schedule, Manual, Tool])
