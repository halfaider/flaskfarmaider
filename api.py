import traceback
import urllib.parse
import sqlite3
import functools
from threading import Thread
from typing import Any

import flask
import requests
from flask_sqlalchemy.query import Query
from sqlalchemy.orm.attributes import InstrumentedAttribute

from .constants import *
from .util import ThreadHasReturn
from .setup import FRAMEWORK, PLUGIN, LOGGER, CONFIG
from .setup import (
    PluginBase, PluginModuleBase, PluginPageBase, ModelBase,
    default_route_socketio_module, default_route_socketio_page, celery_is_active
)


class Base:

    _DB_VERSIONS = ['1']

    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)

    def set_recent_menu(self, req: flask.Request) -> None:
        current_menu = '|'.join(req.path[1:].split('/')[1:])
        if not current_menu == CONFIG.get('recent_menu_plugin'):
            CONFIG.set('recent_menu_plugin', current_menu)

    def get_template_args(self) -> dict:
        args = {
            'package_name': PLUGIN.package_name,
            'module_name': self.name if isinstance(self, ModuleBase) else self.parent.name,
            'page_name': self.name if isinstance(self, PageBase) else None,
        }
        return args

    def prerender(self, sub: str, req: flask.Request) -> None:
        self.set_recent_menu(req)

    def run_async(self, func: callable, args: tuple = (), kwargs: dict = {}, **opts) -> None:
        if celery_is_active():
            result = func.apply_async(args=args, kwargs=kwargs, link=self.celery_link.s(), **opts)
            # 결과는 serve 중인 메인 스레드에 출력해야 하므로
            Thread(target=result.get, kwargs={'on_message': self.callback_sio, 'propagate': False}, daemon=True).start()
            LOGGER.debug(f'Run by celery: {func.__name__}()')
        else:
            th = ThreadHasReturn(target=func, args=args, kwargs=kwargs, daemon=True, callback=self.callback_sio)
            th.start()
            LOGGER.debug(f'Run by Thread: {func.__name__}()')

    @FRAMEWORK.celery.task
    def celery_link(result) -> None:
        pass

    def callback_sio(self, data: dict) -> None:
        self.socketio_callback('result', {'status': data.get('status'), 'data': data.get('result')})

    def process_command(self, command: str, arg1: str, arg2: str, arg3: str, request: flask.Request) -> flask.Response:
        try:
            data = getattr(self, f'command_{command}', self.command_default)(request)
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            data = self.returns('warning', str(e))
        finally:
            return flask.jsonify(data)

    def parse_command(self, request: flask.Request) -> dict[str, Any]:
        query = urllib.parse.parse_qs(request.form.get('arg1'), keep_blank_values=True)
        ids = list(map(int, query.pop('id', [-1])))
        return {
            'command': request.form.get('command'),
            'query': query,
            'ids': ids,
        }

    def command_default(self, request: flask.Request) -> tuple[bool, str]:
        data = self.returns('danger', title='Flaskfarmaider')
        data['msg'] = '아직 구현되지 않았습니다.'
        return data

    def returns(self, success: str, msg: str = None, title: str = None, modal: str = None, json: dict = None, reload: bool = False, data: dict = None) -> dict:
        return {'ret': success, 'msg': msg, 'title': title, 'modal': modal, 'json': json, 'reload': reload, 'data': data}

    def _migration(self, version_key: str, table: str, migrate_func: callable) -> None:
        version = CONFIG.get(version_key) or self._DB_VERSIONS[0]
        LOGGER.debug(f'{table} 현재 DB 버전: {version}')
        with FRAMEWORK.app.app_context():
            db_file = FRAMEWORK.app.config['SQLALCHEMY_BINDS'][PLUGIN.package_name].replace('sqlite:///', '').split('?')[0]
            try:
                with sqlite3.connect(db_file) as conn:
                    conn.row_factory = sqlite3.Row
                    cs = conn.cursor()
                    # DB 볼륨 정리
                    cs.execute('VACUUM;')
                    for ver in self._DB_VERSIONS[(self._DB_VERSIONS.index(version)):]:
                        migrate_func(ver, table, cs)
                        version = ver
                    FRAMEWORK.db.session.flush()
                LOGGER.debug(f'{table} 최종 DB 버전: {version}')
                CONFIG.set(version_key, version)
            except:
                LOGGER.error(traceback.format_exc())
                LOGGER.error('마이그레이션 실패')


class ModuleBase(Base, PluginModuleBase):

    def __init__(self, plugin: PluginBase, first_menu: str = None, name: str = None, scheduler_desc: str = None) -> None:
        super().__init__(plugin, first_menu, name, scheduler_desc)
        default_route_socketio_module(self)
        self.db_default = {}

    def get_module(self, module_name: str) -> PluginModuleBase | None:
        '''override'''
        return super().get_module(module_name)

    def set_page_list(self, page_list: list[PluginPageBase]) -> None:
        '''override'''
        super().set_page_list(page_list)

    def get_page(self, page_name: str) -> PluginPageBase | None:
        '''override'''
        return super().get_page(page_name)

    def process_menu(self, sub: str, req: flask.Request) -> flask.Response:
        '''override'''
        self.prerender(sub, req)
        try:
            if self.page_list:
                if sub:
                    page_ins = self.get_page(sub)
                else:
                    page_ins = self.get_page(self.get_first_menu())
                return page_ins.process_menu(req)
            else:
                args = self.get_template_args()
                return flask.render_template(f'{PLUGIN.package_name}_{self.name}.html', args=args)
        except:
            LOGGER.error(traceback.format_exc())
            return flask.render_template('sample.html', title=f"process_menu() - {PLUGIN.package_name}/{self.name}/{sub}")

    def process_ajax(self, sub: str, req: flask.Request) -> flask.Response:
        '''override'''
        return super().process_ajax(sub, req)

    def process_command(self, command: str, arg1: str, arg2: str, arg3: str, req: flask.Request) -> flask.Response:
        '''override'''
        return super().process_command(command, arg1, arg2, arg3, req)

    def process_api(self, sub: str, req: flask.Request) -> flask.Response:
        '''override'''
        return super().process_api(sub, req)

    def process_normal(self, sub: str, req: flask.Request) -> flask.Response:
        '''override'''
        return super().process_normal(sub, req)

    def scheduler_function(self) -> None:
        '''override'''
        super().scheduler_function()

    def db_delete(self, day: int | str) -> int:
        '''override'''
        return super().db_delete(day)

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()

    def plugin_load_celery(self) -> None:
        '''override'''
        super().plugin_load_celery()

    def plugin_unload(self) -> None:
        '''override'''
        super().plugin_unload()

    def setting_save_after(self, change_list: list) -> None:
        '''override'''
        super().setting_save_after(change_list)

    def process_telegram_data(self, data: dict, target: str = None) -> None:
        '''override'''
        super().process_telegram_data(data, target=target)

    def migration(self) -> None:
        '''override'''
        super().migration()

    def get_scheduler_desc(self) -> str:
        '''override'''
        return super().get_scheduler_desc()

    def get_scheduler_interval(self) -> str:
        '''override'''
        return super().get_scheduler_interval()

    def get_first_menu(self) -> str:
        '''override'''
        return super().get_first_menu()

    def get_scheduler_id(self) -> str:
        '''override'''
        return super().get_scheduler_id()

    def dump(self, data) -> str:
        '''override'''
        return super().dump(data)

    def socketio_connect(self) -> None:
        '''override'''
        super().socketio_connect()

    def socketio_disconnect(self) -> None:
        '''override'''
        super().socketio_disconnect()

    def arg_to_dict(self, args: str) -> dict:
        '''override'''
        return super().arg_to_dict(args)

    def get_scheduler_name(self) -> str:
        '''override'''
        return super().get_scheduler_name()

    def process_discord_data(self, data: dict) -> None:
        '''override'''
        super().process_discord_data(data)

    def start_celery(self, func: callable, *args, on_message: callable = None, page: PluginPageBase = None) -> dict:
        '''override'''
        if FRAMEWORK.config['use_celery']:
            result = func.apply_async(args)
            try:
                if on_message != None:
                    ret = result.get(on_message=on_message, propagate=True)
                else:
                    ret = result.get()
            except:
                ret = result.get()
        else:
            if on_message == None:
                ret = func(*args)
            else:
                if page == None:
                    ret = func(self, *args)
                else:
                    ret = func(page, *args)
        return ret


class PageBase(Base, PluginPageBase):

    def __init__(self, plugin: PluginBase, parent: PluginModuleBase, name: str = None, scheduler_desc: str = None) -> None:
        super().__init__(plugin, parent, name, scheduler_desc)
        default_route_socketio_page(self)
        self.db_default = {}

    def process_menu(self, req: flask.Request) -> flask.Response:
        '''override'''
        self.prerender(self.name, req)
        try:
            args = self.get_template_args()
            return flask.render_template(f'{PLUGIN.package_name}_{self.parent.name}_{self.name}.html', args=args)
        except:
            self.P.logger.error(traceback.format_exc())
            return flask.render_template('sample.html', title=f"process_menu() - {PLUGIN.package_name}/{self.parent.name}/{self.name}")

    def process_ajax(self, sub: str, req: flask.Request) -> flask.Response:
        '''override'''
        return super().process_ajax(sub, req)

    def process_api(self, sub: str, req: flask.Request) -> flask.Response:
        '''override'''
        return super().process_api(sub, req)

    def process_normal(self, sub: str, req: flask.Request) -> flask.Response:
        '''override'''
        return super().process_normal(sub, req)

    def process_command(self, command: str, arg1: str, arg2: str, arg3: str, req: flask.Request) -> flask.Response:
        '''override'''
        return super().process_command(command, arg1, arg2, arg3, req)

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()

    def plugin_load_celery(self) -> None:
        '''override'''
        super().plugin_load_celery()

    def plugin_unload(self) -> None:
        '''override'''
        super().plugin_unload()

    def scheduler_function(self) -> None:
        '''override'''
        super().scheduler_function()

    def get_scheduler_desc(self) -> str:
        '''override'''
        return super().get_scheduler_desc()

    def get_scheduler_interval(self) -> str:
        '''override'''
        return super().get_scheduler_interval()

    def get_scheduler_name(self) -> str:
        '''override'''
        return super().get_scheduler_name()

    def migration(self) -> None:
        '''override'''
        super().migration()

    def setting_save_after(self, change_list: list) -> None:
        '''override'''
        super().setting_save_after(change_list)

    def process_telegram_data(self, data: dict, target: str = None) -> None:
        '''override'''
        super().process_telegram_data(data, target=target)

    def arg_to_dict(self, args: str) -> dict:
        '''override'''
        return super().arg_to_dict(args)

    def get_page(self, page_name) -> PluginPageBase:
        '''override'''
        return super().get_page(page_name)

    def get_module(self, module_name) -> PluginModuleBase:
        '''override'''
        return super().get_module(module_name)

    def process_discord_data(self, data: dict) -> None:
        '''override'''
        super().process_discord_data(data)

    def db_delete(self, day: int | str) -> int:
        '''override'''
        return super().db_delete(day)

    def start_celery(self, func: callable, *args, on_message: callable = None) -> dict:
        '''override'''
        return self.parent.start_celery(func, *args, on_message, page=self)

    def socketio_connect(self) -> None:
        pass

    def socketio_disconnect(self) -> None:
        pass


class Model(ModelBase):

    __abstract__ = True
    __bind_key__ = PLUGIN.package_name
    P = PLUGIN

    def as_dict(self) -> dict:
        '''override'''
        return super().as_dict()

    def save(self) -> None:
        '''override'''
        super().save()

    @classmethod
    def get_paging_info(cls, count: int, current_page: int, page_size: int) -> dict | None:
        '''override'''
        return super().get_paging_info(count, current_page, page_size)

    @classmethod
    def get_by_id(cls, id) -> ModelBase:
        '''override'''
        return super().get_by_id(id)

    @classmethod
    def get_list(cls, by_dict: bool = False) -> list | None:
        '''override'''
        return super().get_list(by_dict)

    @classmethod
    def delete_by_id(cls, id: int) -> bool:
        '''override'''
        return super().delete_by_id(id)

    @classmethod
    def delete_all(cls, day: int | str | None = None) -> int:
        '''override'''
        return super().delete_all(day)

    @classmethod
    def web_list(cls, req: flask.Request) -> dict:
        '''override'''
        return super().web_list(req)

    @classmethod
    def make_query(cls, req: flask.Request, order: str = 'desc', search: str = '', option1: str = 'all', option2: str = 'all') -> Query:
        '''override'''
        return super().make_query(req, order, search, option1, option2)

    @classmethod
    def make_query_search(cls, query: Query, search: str, field: InstrumentedAttribute) -> Query:
        '''override'''
        return super().make_query_search(query, search, field)

    @classmethod
    def get_list_by_status(cls, status: str) -> list:
        '''override'''
        return super().get_list_by_status(status)


class Aider:

    def __init__(self, name: str = None) -> None:
        self.name = name

    def request(self, method: str, url: str, *args: tuple, **kwds: dict) -> requests.Response:
        try:
            timeout_ = int(CONFIG.get('setting_general_timeout'))
        except:
            LOGGER.error(traceback.format_exc())
            timeout_ = 0
        kwds['timeout'] = timeout_ if timeout_ > 0 else kwds.get('timeout')
        try:
            if method.upper() == 'JSON':
                data = kwds.pop('data', None)
                return requests.request('POST', url, *args, json=data, **kwds)
            else:
                return requests.request(method, url, *args, **kwds)
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            LOGGER.error(url)
            response = requests.Response()
            response._content = bytes(str(e), 'utf-8')
            response.status_code = 0
            return response


class PluginAider(Aider):

    def __init__(self, name: str) -> None:
        super().__init__(name)

    @property
    def plugin(self) -> PluginModuleBase | None:
        return FRAMEWORK.PluginManager.get_plugin_instance(self.name)

    def check_plugin(func: callable) -> callable:
        @functools.wraps(func)
        def wrap(self, *args, **kwds):
            if self.plugin:
                return func(self, *args, **kwds)
            else:
                raise Exception(f'플러그인을 찾을 수 없습니다: {self.name}')
        return wrap

    @check_plugin
    def get_module(self, module: str) -> PluginModuleBase:
        return self.plugin.logic.get_module(module)
