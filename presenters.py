import json
import traceback
import urllib
from threading import Thread
import sqlite3
import time
import functools
import logging

import flask
import flask_login

from .setup import PluginBase, PluginModuleBase, PluginPageBase, system_plugin, default_route_socketio_module, ModelBase, FrameworkJob
from .setup import FRAMEWORK, PLUGIN, LOGGER, CONFIG
from .models import Job
from .aiders import BrowserAider, SettingAider, JobAider, PlexmateAider, GDSToolAider, RcloneAider
from .migrations import migrate_schedule, migrate_setting
from .constants import *

CELERY_INSPECT = FRAMEWORK.celery.control.inspect()
CELERY_ACTIVE = False


def check_celery() -> None:
    global CELERY_ACTIVE
    while True:
        CELERY_ACTIVE = True if CELERY_INSPECT.active() else False
        time.sleep(5)


Thread(target=check_celery, daemon=True).start()


class ThreadHasReturn(Thread):

    def __init__(self, group=None, target: callable = None, name: str = None, args: tuple | list = (),
                 kwargs: dict = {}, daemon: bool = None, callback: callable = None) -> None:
        Thread.__init__(self, group, target, name, args, kwargs, daemon=daemon)
        self._return = None
        self.callback = callback

    def run(self) -> None:
        if self._target:
            self._return = self._target(*self._args, **self._kwargs)
        if self.callback:
            self.callback(self.get_return())

    def join(self, *args) -> dict:
        Thread.join(self, *args)
        return self.get_return()

    def get_return(self) -> dict:
        # celery status: SUCCESS, STARTED, REVOKED, RETRY, RECEIVED, PENDING, FAILURE
        return {
            'status': 'SUCCESS',
            'result': self._return,
        }


class Base:

    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        default_route_socketio_module(self)
        self.commands = {
            'default': self.command_default,
        }

    def set_recent_menu(self, req: flask.Request) -> None:
        current_menu = '|'.join(req.path[1:].split('/')[1:])
        if not current_menu == CONFIG.get('recent_menu_plugin'):
            CONFIG.set('recent_menu_plugin', current_menu)

    def get_template_args(self) -> dict:
        args = {
            'package_name': PLUGIN.package_name,
            'module_name': self.name if isinstance(self, BaseModule) else self.parent.name,
            'page_name': self.name if isinstance(self, BasePage) else None,
        }
        return args

    def prerender(self, sub: str, req: flask.Request) -> None:
        self.set_recent_menu(req)

    def task_command(self, task: str, target: str, vfs: str, scan: str) -> tuple[bool, str]:
        vfs, recursive = vfs.split('|')
        if recursive:
            recursive = True if recursive.lower() == 'true' else False
        else:
            recursive = False
        if scan:
            scan_mode, periodic_id = scan.split('|')
        else:
            scan_mode = SCAN_MODE_KEYS[0]
            periodic_id = '-1'
        if target:
            job = {
                'task': task,
                'target': target,
                'recursive': recursive,
                'scan_mode': scan_mode,
                'periodic_id': int(periodic_id) if periodic_id else -1,
                'vfs': vfs,
            }
            self.run_async(self.start_job, (Job.get_job(info=job),))
            result, msg = True, '작업을 실행했습니다.'
        else:
            result, msg = False, '경로 정보가 없습니다.'
        return result, msg

    def run_async(self, func: callable, args: tuple = (), kwargs: dict = {}, **opts) -> None:
        if CELERY_ACTIVE:
            result = func.apply_async(args=args, kwargs=kwargs, link=self.celery_link.s(), **opts)
            # 결과는 serve 중인 메인 스레드에 출력해야 하므로
            Thread(target=result.get, kwargs={'on_message': self.callback_sio, 'propagate': False}, daemon=True).start()
        else:
            th = ThreadHasReturn(target=func, args=args, kwargs=kwargs, daemon=True, callback=self.callback_sio)
            th.start()

    @FRAMEWORK.celery.task
    def celery_link(result) -> None:
        pass

    @FRAMEWORK.celery.task(bind=True)
    def start_job(self, job: ModelBase) -> dict:
        try:
            if job.id and job.id > 0:
                job.set_status(STATUS_KEYS[1])
            if job.task in TOOL_TRASH_KEYS:
                CONFIG.set(TOOL_TRASH_TASK_STATUS, STATUS_KEYS[1])
            job_aider = JobAider()
            job_aider.starts.get(job.task)(job)
            msg = '작업이 끝났습니다.'
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            msg = str(e)
        finally:
            if job.id and job.id > 0:
                job.set_status(STATUS_KEYS[2])
            if job.task in TOOL_TRASH_KEYS:
                CONFIG.set(TOOL_TRASH_TASK_STATUS, STATUS_KEYS[0])
            job = job.as_dict()
            job['msg'] = msg
            return job

    def callback_sio(self, data: dict) -> None:
        self.socketio_callback('result', {'status': data.get('status'), 'data': data.get('result')})

    def process_command(self, command: str, arg1: str, arg2: str, arg3: str, request: flask.Request) -> flask.Response:
        try:
            data = self.commands.get(command, self.commands.get('default'))(request)
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            data = self.returns('warning', str(e))
        finally:
            return flask.jsonify(data)

    def command_default(self, request: flask.Request) -> dict:
        command = request.form.get('command')
        if command in TASK_KEYS:
            result, msg = self.task_command(command, request.form.get('arg1'), request.form.get('arg2'), request.form.get('arg3'))
        else:
            result, msg = False, f'알 수 없는 명령입니다: {command}'
        return self.returns('success' if result else 'warning', msg)

    def returns(self, success: str, msg: str = None, title: str = None, modal: str = None, json: dict = None, reload: bool = False, data: dict = None) -> dict:
        return {'ret': success, 'msg': msg, 'title': title, 'modal': modal, 'json': json, 'reload': reload, 'data': data}

    def create_schedule_id(self, job_id: int, middle: str = SCHEDULE) -> str:
        return f'{PLUGIN.package_name}_{middle}_{job_id}'

    def add_schedule(self, id: int, job: ModelBase = None) -> bool:
        try:
            job = job or Job.get_by_id(id)
            schedule_id = self.create_schedule_id(job.id)
            if not FRAMEWORK.scheduler.is_include(schedule_id):
                sch = FrameworkJob(__package__, schedule_id, job.schedule_interval, self.run_async, job.desc, args=(self.start_job, (job,)))
                FRAMEWORK.scheduler.add_job_instance(sch)
            return True
        except:
            LOGGER.error(traceback.format_exc())
            return False

    def set_schedule(self, job_id: int | str, active: bool = False) -> tuple[bool, str]:
        schedule_id = self.create_schedule_id(job_id)
        is_include = FRAMEWORK.scheduler.is_include(schedule_id)
        job = Job.get_by_id(job_id)
        schedule_mode = job.schedule_mode if job else FF_SCHEDULE_KEYS[0]
        if active and is_include:
            result, data = False, f'이미 일정에 등록되어 있습니다.'
        elif not active and is_include:
            result, data = FRAMEWORK.scheduler.remove_job(schedule_id), '일정에서 제외했습니다.'
        elif not active and not is_include:
            result, data = False, '등록되지 않은 일정입니다.'
        elif active and not is_include and schedule_mode == FF_SCHEDULE_KEYS[2]:
            result = self.add_schedule(job_id)
            data = '일정에 등록했습니다.' if result else '일정에 등록하지 못했어요.'
        else:
            result, data = False, '등록할 수 없는 일정 방식입니다.'
        return result, data

    def schedule_reload(self, job: Job, old_job: Job) -> Job:
        msg = ''
        schedule_id = self.create_schedule_id(job.id)
        if FRAMEWORK.scheduler.is_include(schedule_id) and \
            (old_job.schedule_mode != job.schedule_mode or \
            old_job.schedule_interval != job.schedule_interval):
            for _ in range(0, 60):
                FRAMEWORK.scheduler.remove_job(schedule_id)
                if not FRAMEWORK.scheduler.is_include(schedule_id):
                    break
                time.sleep(1)
            if job.schedule_mode == FF_SCHEDULE_KEYS[2]:
                if FRAMEWORK.scheduler.is_include(schedule_id):
                    msg = f'일정을 재등록 하지 못 했습니다: {schedule_id}'
                else:
                    self.add_schedule(job.id)
                    msg = f'일정을 재등록 했습니다: {schedule_id}'
                LOGGER.debug(msg)
        job = job.as_dict()
        job['is_include'] = FRAMEWORK.scheduler.is_include(schedule_id)
        job['msg'] = msg
        return job

    def get_client_ip(self, request: flask.Request) -> str:
        try:
            if 'X-Real-Ip' in request.headers:
                remote_addr = request.headers.getlist("X-Real-IP")[0].rpartition(' ')[-1]
            if 'X-Forwarded-For' in request.headers:
                remote_addr = request.headers.getlist("X-Forwarded-For")[0].rpartition(' ')[-1]
            else:
                remote_addr = request.remote_addr or 'unknown'
        except:
            LOGGER.error(traceback.format_exc())
            remote_addr = 'unknown'
        return remote_addr

    def _migration(self, version: str, versions: list, table: str, migrate_func: callable) -> str:
        LOGGER.debug(f'{table} 현재 DB 버전: {version}')
        with FRAMEWORK.app.app_context():
            db_file = FRAMEWORK.app.config['SQLALCHEMY_BINDS'][PLUGIN.package_name].replace('sqlite:///', '').split('?')[0]
            conn = sqlite3.connect(db_file)
            try:

                with conn:
                    conn.row_factory = sqlite3.Row
                    cs = conn.cursor()
                    # DB 볼륨 정리
                    cs.execute(f'VACUUM;')
                    for ver in versions[(versions.index(version)):]:
                        migrate_func(ver, table, cs)
                        version = ver
                    FRAMEWORK.db.session.flush()
            except:
                LOGGER.exception('마이그레이션 실패')
            conn.close()
        LOGGER.debug(f'{table} 최종 DB 버전: {version}')
        return version



class BaseModule(Base, PluginModuleBase):

    def __init__(self, plugin: PluginBase, first_menu: str = None, name: str = None, scheduler_desc: str = None) -> None:
        super().__init__(plugin, first_menu, name, scheduler_desc)
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


class BasePage(Base, PluginPageBase):

    def __init__(self, plugin: PluginBase, parent: PluginModuleBase, name: str = None, scheduler_desc: str = None) -> None:
        super().__init__(plugin, parent, name, scheduler_desc)
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


class Setting(BaseModule):

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name=SETTING)
        self.db_default = {
            SETTING_DB_VERSION: SETTING_DB_VERSIONS[-1],
            SETTING_RCLONE_REMOTE_ADDR: 'http://172.17.0.1:5572',
            SETTING_RCLONE_REMOTE_VFS: '',
            SETTING_RCLONE_REMOTE_VFSES: '',
            SETTING_RCLONE_REMOTE_USER: '',
            SETTING_RCLONE_REMOTE_PASS: '',
            SETTING_RCLONE_MAPPING: '/mnt/gds:\n/home/cloud/sjva/VOD:/VOD',
            SETTING_PLEXMATE_MAX_SCAN_TIME: '60',
            SETTING_PLEXMATE_TIMEOVER_RANGE: '0~0',
            SETTING_PLEXMATE_PLEX_MAPPING: '',
            SETTING_STARTUP_EXECUTABLE: 'false',
            SETTING_STARTUP_COMMANDS: 'apt-get update',
            SETTING_STARTUP_TIMEOUT: '300',
            SETTING_STARTUP_DEPENDENCIES: SettingAider().depends(),
            SETTING_GDS_TOOL_REQUEST_SPAN: '30',
            SETTING_GDS_TOOL_REQUEST_AUTO: 'false',
            SETTING_GDS_TOOL_FP_SPAN: '30',
            SETTING_GDS_TOOL_FP_AUTO: 'false',
            SETTING_LOGGING_LOGIN: 'false',
            SETTING_LOGGING_ACCESS: 'false',
            SETTING_LOGGING_ACCESS_FILE: '/data/log/access.log',
            SETTING_LOGGING_ACCESS_FORMAT: '{remote} {method} "{path}" {status}'
        }
        self.commands.update({'command_test_connection': self.command_test_conn})
        self.system_route = system_plugin.logic.get_module('route')
        self.system_route_process_command = self.system_route.process_command
        self.commands['clear_db'] = self.command_clear_db

    def prerender(self, sub: str, req: flask.Request) -> None:
        '''override'''
        super().prerender(sub, req)
        # yaml 파일 우선
        CONFIG.set(SETTING_STARTUP_DEPENDENCIES, SettingAider().depends())

    def get_template_args(self) -> dict:
        '''override'''
        args = super().get_template_args()
        args[SETTING_RCLONE_REMOTE_ADDR] = CONFIG.get(SETTING_RCLONE_REMOTE_ADDR)
        args[SETTING_RCLONE_REMOTE_VFS] = CONFIG.get(SETTING_RCLONE_REMOTE_VFS)
        args[SETTING_RCLONE_REMOTE_VFSES] = CONFIG.get(SETTING_RCLONE_REMOTE_VFSES)
        args[SETTING_RCLONE_REMOTE_USER] = CONFIG.get(SETTING_RCLONE_REMOTE_USER)
        args[SETTING_RCLONE_REMOTE_PASS] = CONFIG.get(SETTING_RCLONE_REMOTE_PASS)
        args[SETTING_RCLONE_MAPPING] = CONFIG.get(SETTING_RCLONE_MAPPING)
        args[SETTING_PLEXMATE_MAX_SCAN_TIME] = CONFIG.get(SETTING_PLEXMATE_MAX_SCAN_TIME)
        args[SETTING_PLEXMATE_TIMEOVER_RANGE] = CONFIG.get(SETTING_PLEXMATE_TIMEOVER_RANGE)
        args[SETTING_PLEXMATE_PLEX_MAPPING] = CONFIG.get(SETTING_PLEXMATE_PLEX_MAPPING)
        args[SETTING_STARTUP_EXECUTABLE] = CONFIG.get(SETTING_STARTUP_EXECUTABLE)
        args[SETTING_STARTUP_COMMANDS] = CONFIG.get(SETTING_STARTUP_COMMANDS)
        args[SETTING_STARTUP_TIMEOUT] = CONFIG.get(SETTING_STARTUP_TIMEOUT)
        args[SETTING_STARTUP_DEPENDENCIES] = CONFIG.get(SETTING_STARTUP_DEPENDENCIES)

        args[SETTING_GDS_TOOL_REQUEST_SPAN] = CONFIG.get(SETTING_GDS_TOOL_REQUEST_SPAN)
        args[SETTING_GDS_TOOL_REQUEST_AUTO] = CONFIG.get(SETTING_GDS_TOOL_REQUEST_AUTO)
        args[SETTING_GDS_TOOL_FP_SPAN] = CONFIG.get(SETTING_GDS_TOOL_FP_SPAN)
        args[SETTING_GDS_TOOL_FP_AUTO] = CONFIG.get(SETTING_GDS_TOOL_FP_AUTO)
        args[SETTING_LOGGING_LOGIN] = CONFIG.get(SETTING_LOGGING_LOGIN)
        args[SETTING_LOGGING_LOGIN_FILE] = f"{FRAMEWORK.config['path_data']}/log/{system_plugin.package_name}.log"
        args[SETTING_LOGGING_ACCESS] = CONFIG.get(SETTING_LOGGING_ACCESS)
        args[SETTING_LOGGING_ACCESS_FILE] = CONFIG.get(SETTING_LOGGING_ACCESS_FILE)
        args[SETTING_LOGGING_ACCESS_FORMAT] = CONFIG.get(SETTING_LOGGING_ACCESS_FORMAT)
        try:
            gdsaider = GDSToolAider()
            args[SETTING_GDS_TOOL_REQUEST_TOTAL] = gdsaider.get_total_records('request')
            args[SETTING_GDS_TOOL_FP_TOTAL] = gdsaider.get_total_records('fp')
        except:
            LOGGER.error(traceback.format_exc())
            args[SETTING_GDS_TOOL_REQUEST_TOTAL] = -1
            args[SETTING_GDS_TOOL_FP_TOTAL] = -1
        return args

    def migration(self) -> None:
        '''override'''
        super().migration()
        version = CONFIG.get(SETTING_DB_VERSION) or SETTING_DB_VERSIONS[0]
        version = self._migration(version, SETTING_DB_VERSIONS, f'{PLUGIN.package_name}_setting', migrate_setting)
        CONFIG.set(SETTING_DB_VERSION, version)

    def command_test_conn(self, request: flask.Request) -> dict:
        response = RcloneAider()._vfs_list()
        data = {'title': 'Rclone Remote', 'modal': response.text}
        if int(str(response.status_code)[0]) == 2:
            data['ret'] = 'success'
            data['msg'] = '접속에 성공했습니다.'
            vfses = sorted(response.json()['vfses'])
            CONFIG.set(SETTING_RCLONE_REMOTE_VFSES, '|'.join(vfses))
            data['vfses'] = vfses
        else:
            data['ret'] = 'warning'
            data['msg'] = '접속에 실패했습니다.'
        return data

    def command_clear_db(self, request: flask.Request) -> dict:
        mod = request.form.get('arg1')
        span = int(request.form.get('arg2'))
        GDSToolAider().delete(mod, span)
        return self.returns('success', 'DB 정리를 실행합니다.')

    def command_default(self, request: flask.Request) -> tuple[bool, str]:
        '''override'''
        return super().command_default(request)

    def setting_save_after(self, changes: list) -> None:
        '''override'''
        super().setting_save_after(changes)
        for change in changes:
            if change == f'{self.name}_startup_dependencies':
                SettingAider().depends(CONFIG.get(SETTING_STARTUP_DEPENDENCIES))
            if change == SETTING_LOGGING_LOGIN:
                enable = CONFIG.get(SETTING_LOGGING_LOGIN)
                if enable.lower() == 'true':
                    self.system_route.process_command = self.process_command_route_system
                else:
                    self.system_route.process_command = self.system_route_process_command

    def process_command_route_system(self, command: str, arg1: str | None, arg2: str | None, arg3: str | None, request: flask.Request) -> flask.Response:
        '''alternative of system.route.process_command()'''
        if command == 'login':
            username = arg1
            password = arg2
            remember = (arg3 == 'true')
            client_info = f"user={username} ip={self.get_client_ip(request)}"
            failed_msg = f'로그인 실패: {client_info}'
            if username not in FRAMEWORK.users:
                system_plugin.logger.warning(failed_msg)
                return flask.jsonify('no_id')
            elif not FRAMEWORK.users[username].can_login(password):
                system_plugin.logger.warning(failed_msg)
                return flask.jsonify('wrong_password')
            else:
                system_plugin.logger.info(f'로그인 성공: {client_info}')
                FRAMEWORK.users[username].authenticated = True
                flask_login.login_user(FRAMEWORK.users[username], remember=remember)
                return flask.jsonify('redirect')

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()
        if not CONFIG.get(SETTING_RCLONE_REMOTE_VFSES) and CONFIG.get(SETTING_RCLONE_REMOTE_VFS):
            vfses = RcloneAider().vfs_list()
            CONFIG.set(SETTING_RCLONE_REMOTE_VFSES, '|'.join(vfses))
        if (True if CONFIG.get(SETTING_GDS_TOOL_REQUEST_AUTO).lower() == 'true' else False):
            GDSToolAider().delete('request', CONFIG.get_int(SETTING_GDS_TOOL_REQUEST_SPAN))
        if (True if CONFIG.get(SETTING_GDS_TOOL_FP_AUTO).lower() == 'true' else False):
            GDSToolAider().delete('fp', CONFIG.get_int(SETTING_GDS_TOOL_FP_SPAN))
        if CONFIG.get(SETTING_LOGGING_LOGIN).lower() == 'true':
            self.system_route.process_command = self.process_command_route_system
        if CONFIG.get(SETTING_LOGGING_ACCESS).lower() == 'true':
            self.set_access_log()

    def set_access_log(self) -> None:
        log_file = CONFIG.get(SETTING_LOGGING_ACCESS_FILE) or f"{FRAMEWORK.config.get('path_data', '/data')}/log/access.log"
        level = FRAMEWORK.SystemModelSetting.get_int('log_level') or logging.DEBUG
        logger = self.get_rotating_file_logger(log_file, level=level)

        @FRAMEWORK.app.after_request
        def after_request(response: flask.Response) -> flask.Response:
            request = flask.request
            namespace = {
                'remote': self.get_client_ip(request),
                'method': request.method,
                'scheme': request.scheme,
                'path': request.full_path,
                'status': response.status_code,
                'agent': request.user_agent,
                'length': response.content_length,
            }
            log_format = CONFIG.get(SETTING_LOGGING_ACCESS_FORMAT)
            if not log_format:
                log_format = '{remote} {method} "{path}" {status}'
                CONFIG.set(SETTING_LOGGING_ACCESS_FORMAT, log_format)
            try:
                logger.log(level, log_format.format(**namespace))
            except:
                LOGGER.exception(f'엑세스 로그 형식: {log_format}')
            return response

    def get_rotating_file_logger(self,
                                 path: str,
                                 name: str = None,
                                 fmt: logging.Formatter = logging.Formatter(u'[%(asctime)s] %(message)s'),
                                 max_bytes: int = 5 * 1024 * 1024,
                                 level: int = logging.DEBUG) -> logging.Logger:
        log_file = pathlib.Path(path)
        if not name:
            name = log_file.name
        logger = logging.getLogger(name)
        handler = logging.handlers.RotatingFileHandler(filename=log_file, maxBytes=max_bytes, backupCount=5, encoding='utf8', delay=True)
        handler.setFormatter(fmt)
        logger.setLevel(level)
        logger.addHandler(handler)
        return logger


class Schedule(BaseModule):

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name=SCHEDULE)
        self.db_default = {
            SCHEDULE_DB_VERSION: SCHEDULE_DB_VERSIONS[-1],
            f'{self.name}_working_directory': '/',
            f'{self.name}_last_list_option': ''
        }
        self.web_list_model = Job
        self.commands.update(
            {
                'list': self.command_list,
                'save': self.command_save,
                'delete': self.command_delete,
                'execute': self.command_execute,
                'schedule': self.command_schedule,
                'get_job': self.command_get_job,
            }
        )

    def migration(self) -> None:
        '''override'''
        super().migration()
        version = CONFIG.get(SCHEDULE_DB_VERSION)
        version = self._migration(version, SCHEDULE_DB_VERSIONS, f'{PLUGIN.package_name}_jobs', migrate_schedule)
        CONFIG.set(SCHEDULE_DB_VERSION, version)

    def get_template_args(self) -> dict:
        '''override'''
        args = super().get_template_args()
        args[f'{self.name}_working_directory'] = CONFIG.get(SCHEDULE_WORKING_DIRECTORY)
        args[f'{self.name}_last_list_option'] = CONFIG.get(SCHEDULE_LAST_LIST_OPTION)
        args[SETTING_RCLONE_REMOTE_VFS] = CONFIG.get(SETTING_RCLONE_REMOTE_VFS)
        args[SETTING_RCLONE_REMOTE_VFSES] = CONFIG.get(SETTING_RCLONE_REMOTE_VFSES)
        try:
            plexmateaider = PlexmateAider()
            args['periodics'] = plexmateaider.get_periodics()
            args['sections'] = plexmateaider.get_sections()
        except:
            LOGGER.error(traceback.format_exc())
            args['periodics'] = []
            args['sections'] = []
        args['task_keys'] = TASK_KEYS
        args['tasks'] = TASKS
        args['statuses'] = STATUSES
        args['status_keys'] = STATUS_KEYS
        args['ff_schedule_keys'] = FF_SCHEDULE_KEYS
        args['ff_schedules'] = FF_SCHEDULES
        args['scan_mode_keys'] = SCAN_MODE_KEYS
        args['scan_modes'] = SCAN_MODES
        args['section_type_keys'] = SECTION_TYPE_KEYS
        args['section_types'] = SECTION_TYPES
        args['search_keys'] = SEARCH_KEYS
        args['searches'] = SEARCHES
        return args

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()
        for job in Job.get_list():
            if job.schedule_mode == FF_SCHEDULE_KEYS[1]:
                self.run_async(self.start_job, (job,))
            elif job.schedule_mode == FF_SCHEDULE_KEYS[2] and job.schedule_auto_start:
                self.add_schedule(job.id)
            if not job.status == STATUS_KEYS[0] and not job.schedule_mode == FF_SCHEDULE_KEYS[1]:
                LOGGER.warning(f'정상적으로 종료되지 않은 작업: {job.id} {job.desc}')
                job.set_status(STATUS_KEYS[0])

    def plugin_unload(self) -> None:
        '''override'''
        super().plugin_unload()
        for job in Job.get_list():
            if not job.status == STATUS_KEYS[0]:
                LOGGER.warning(f'강제로 종료되는 작업: {job.id} {job.desc}')
                job.set_status(STATUS_KEYS[0])

    def command_list(self, request: flask.Request) -> dict:
        path = request.form.get('arg1')
        dir_list = json.dumps(BrowserAider().get_dir(path))
        CONFIG.set(SCHEDULE_WORKING_DIRECTORY, path)
        if dir_list:
            return self.returns('success', data=dir_list)
        else:
            return self.returns('warning', '폴더 목록을 생성할 수 없습니다.')

    def command_save(self, request: flask.Request) -> dict:
        query = urllib.parse.parse_qs(request.form.get('arg1'))
        old_job = Job.get_job(int(query.get('id')[0]))
        job = Job.update_formdata(query)
        if old_job.id > 0:
            th = ThreadHasReturn(target=self.schedule_reload, args=(job, old_job), daemon=True, callback=self.callback_sio)
            th.start()
        if job.id > 0:
            return self.returns('success', '저장했습니다.')
        else:
            return self.returns('warning', '저장할 수 없습니다.')

    def command_delete(self, request: flask.Request) -> dict:
        arg1 = request.form.get('arg1')
        if arg1 == 'selected':
            selected = [ int(_id) for _id in request.form.get('arg2').split('|') ]
            not_deleted = []
            LOGGER.info(f'selected for deletion: {selected}')
            for _id in selected:
                if Job.delete_by_id(_id):
                    self.set_schedule(_id, False)
                else:
                    not_deleted.append(_id)
            if len(not_deleted) > 0:
                LOGGER.warning(f'could not delete: {not_deleted}')
                return self.returns('warning', f'일부는 삭제할 수 없었습니다.')
            else:
                return self.returns('success', f'모두 삭제 했습니다.')
        else:
            job_id = int(arg1)
            if Job.delete_by_id(job_id):
                self.set_schedule(job_id, False)
                return self.returns('success', f'삭제 했습니다: ID {job_id}')
            else:
                return self.returns('warning',  f'삭제할 수 없습니다: ID {job_id}')

    def command_execute(self, request: flask.Request) -> dict:
        job_id = int(request.form.get('arg1'))
        self.run_async(self.start_job, (Job.get_job(job_id),))
        return self.returns('success', '일정을 실행했습니다.')

    def command_schedule(self, request: flask.Request) -> dict:
        job_id = int(request.form.get('arg1'))
        active = True if request.form.get('arg2').lower() == 'true' else False
        result, msg = self.set_schedule(job_id, active)
        return self.returns('success' if result else 'warning', msg)

    def command_get_job(self, request: flask.Request) -> dict:
        job_id = int(request.form.get('arg1'))
        job = Job.get_by_id(job_id)
        if job:
            return self.returns('success', data=job.as_dict())
        else:
            return self.returns('warning', f'일정을 찾을 수 없습니다: ID {job_id}')




class Manual(BaseModule):

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name=MANUAL)

    def get_template_args(self) -> dict:
        '''override'''
        args = super().get_template_args()
        with README.open(encoding='utf-8', newline='\n') as file:
            manual = file.read()
        args['manual'] = manual
        return args


class Tool(BaseModule):

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name=TOOL, first_menu=TOOL_TRASH)
        self.set_page_list([ToolTrash])

    def setting_save_after(self, changes: list) -> None:
        '''override'''
        super().setting_save_after(changes)
        for page in self.page_list:
            page.setting_save_after(changes)


class ToolTrash(BasePage):

    def __init__(self, plugin: PluginBase, parent: PluginModuleBase) -> None:
        super().__init__(plugin, parent, name=TOOL_TRASH)
        self.db_default = {
            TOOL_TRASH_TASK_STATUS: STATUS_KEYS[0],
        }
        self.commands.update(
            {
                'status': self.command_status,
                'list': self.command_list,
                'stop': self.command_stop,
                'delete': self.command_delete,
            }
        )

    def check_status(func: callable) -> callable:
        @functools.wraps(func)
        def wrap(*args, **kwds) -> dict:
            status = CONFIG.get(TOOL_TRASH_TASK_STATUS)
            if status == STATUS_KEYS[0]:
                return func(*args, **kwds)
            else:
                return {'ret': 'warning', 'msg': '작업이 실행중입니다.'}
        return wrap

    def command_status(self, request: flask.Request) -> dict:
        return self.returns('success', data={'status': CONFIG.get(TOOL_TRASH_TASK_STATUS)})

    def command_list(self, request: flask.Request) -> dict:
        section_id = int(request.form.get('arg1'))
        page_no = int(request.form.get('arg2'))
        limit = int(request.form.get('arg3'))
        return self.returns('success', data=PlexmateAider().get_trash_list(section_id, page_no, limit))

    def command_stop(self, request: flask.Request) -> dict:
        status = CONFIG.get(TOOL_TRASH_TASK_STATUS)
        if status == STATUS_KEYS[1] or status == STATUS_KEYS[3]:
            CONFIG.set(TOOL_TRASH_TASK_STATUS, STATUS_KEYS[3])
            return self.returns('success', '작업을 멈추는 중입니다.')
        else:
            return self.returns('warning', '실행중이 아닙니다.')

    @check_status
    def command_delete(self, request: flask.Request) -> dict:
        metadata_id = int(request.form.get('arg1'))
        mediaitem_id = int(request.form.get('arg2'))
        result, msg = PlexmateAider().delete_media(metadata_id, mediaitem_id)
        return self.returns('success' if result else 'warning', msg)

    @check_status
    def command_default(self, request: flask.Request) -> dict:
        '''override'''
        command = request.form.get('command')
        if command in TOOL_TRASH_KEYS:
            job = Job.get_job()
            job.task = command
            job.section_id = int(request.form.get('arg1'))
            job.vfs = request.form.get('arg2')
            self.run_async(self.start_job, (job,))
            return self.returns('success', f'작업을 실행했습니다.')
        else:
            return super().command_default(request)

    def get_template_args(self) -> dict:
        '''override'''
        args = super().get_template_args()
        args['section_type_keys'] = SECTION_TYPE_KEYS
        args['section_types'] = SECTION_TYPES
        try:
            plexmateaider = PlexmateAider()
            args['sections'] = plexmateaider.get_sections()
        except:
            LOGGER.error(traceback.format_exc())
            args['sections'] = []
        args['task_keys'] = TASK_KEYS
        args['tasks'] = TASKS
        args['scan_mode_keys'] = SCAN_MODE_KEYS
        args['scan_modes'] = SCAN_MODES
        args['tool_trash_keys'] = TOOL_TRASH_KEYS
        args['tool_trashes'] = TOOL_TRASHES
        args['status_keys'] = STATUS_KEYS
        args[TOOL_TRASH_TASK_STATUS.lower()] = CONFIG.get(TOOL_TRASH_TASK_STATUS)
        args[SETTING_RCLONE_REMOTE_VFS] = CONFIG.get(SETTING_RCLONE_REMOTE_VFS)
        args[SETTING_RCLONE_REMOTE_VFSES] = CONFIG.get(SETTING_RCLONE_REMOTE_VFSES)
        return args

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()
        CONFIG.set(TOOL_TRASH_TASK_STATUS, STATUS_KEYS[0])

    def plugin_unload(self) -> None:
        '''override'''
        super().plugin_unload()
        CONFIG.set(TOOL_TRASH_TASK_STATUS, STATUS_KEYS[0])
