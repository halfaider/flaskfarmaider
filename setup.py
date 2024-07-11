import json
import traceback

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
from .util import get_client_ip

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
    value = CONFIG.get(key)
    match value.lower():
        case 'true' | 'on' | 'yes':
            value = True
        case 'false' | 'off' | 'no':
            value = False
        case _:
            LOGGER.error(f'Could not determine a boolean type: {value}')
            value = False
    return value


def default_route_socketio_page(page):
    module = page.parent
    page.socketio_list = page.socketio_list or []

    @F.socketio.on('connect', namespace=f'/{P.package_name}/{module.name}/{page.name}')
    def connect():
        P.logger.debug(f'socket_connect : {P.package_name}/{module.name}/{page.name}')
        page.socketio_list.append(request.sid)
        socketio_callback('start', '')
        page.socketio_connect()

    @F.socketio.on('disconnect', namespace=f'/{P.package_name}/{module.name}/{page.name}')
    def disconnect():
        P.logger.debug(f'socket_disconnect : {P.package_name}/{module.name}/{page.name}')
        page.socketio_list.remove(request.sid)
        page.socketio_disconnect()

    def socketio_callback(cmd, data, encoding=True):
        if page.socketio_list:
            if encoding:
                data = json.dumps(data, cls=AlchemyEncoder)
                data = json.loads(data)
            F.socketio.emit(cmd, data, namespace=f'/{P.package_name}/{module.name}/{page.name}')

    page.socketio_callback = socketio_callback


CONFIG.get_json = setting_get_json
CONFIG.set_json = setting_set_json
CONFIG.get_boolean = setting_get_boolean


from .presenters import Setting
from .presenters import Schedule
from .presenters import Manual
from .presenters import Tool

PLUGIN.set_module_list([Setting, Schedule, Manual, Tool])
