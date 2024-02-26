import json
import traceback
import urllib
from threading import Thread
import sqlite3
import time
import functools
import logging

import flask

from .setup import PluginBase, PluginModuleBase, PluginPageBase, default_route_socketio_module, default_route_socketio_page, ModelBase, FrameworkJob
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

    def task_command(self, task: str, query: dict[str, list]) -> tuple[bool, str]:
        target = query.get('target', [])
        if target:
            job = {
                'task': task,
                'target': target[0],
                'recursive': query.get('recursive', ['false'])[0].lower() == 'true',
                'scan_mode': query.get('scan_mode', [SCAN_MODE_KEYS[0]])[0],
                'periodic_id': int(query.get('periodic_id', ['-1'])[0]),
                'vfs': query.get('vfs', ['remote:'])[0],
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

    def pre_command(self, request: flask.Request) -> tuple[str, dict, list]:
        command = request.form.get('command')
        query = urllib.parse.parse_qs(request.form.get('arg1'))
        ids =list(map(int, query.pop('id', [-1])))
        return command, query, ids

    def command_default(self, request: flask.Request) -> dict:
        command, query, ids = self.pre_command(request)
        if command in TASK_KEYS:
            result, msg = self.task_command(command, query)
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

    def reload_schedule(self, job: Job, old_job: Job) -> None:
        th = ThreadHasReturn(target=self._reload_schedule, args=(job, old_job), daemon=True, callback=self.callback_sio)
        th.start()

    def _reload_schedule(self, job: Job, old_job: Job) -> Job:
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


class BasePage(Base, PluginPageBase):

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
            SETTING_STARTUP_DEPENDENCIES: SettingAider.depends(),
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
        self.commands['clear_db'] = self.command_clear_db
        self.commands['check_timeover'] = self.command_check_timeover

    def prerender(self, sub: str, req: flask.Request) -> None:
        '''override'''
        super().prerender(sub, req)
        # yaml 파일 우선
        CONFIG.set(SETTING_STARTUP_DEPENDENCIES, SettingAider.depends())

    def get_template_args(self) -> dict:
        '''override'''
        args = super().get_template_args()
        confs = [
            SETTING_RCLONE_REMOTE_ADDR,
            SETTING_RCLONE_REMOTE_VFS,
            SETTING_RCLONE_REMOTE_VFSES,
            SETTING_RCLONE_REMOTE_USER,
            SETTING_RCLONE_REMOTE_PASS,
            SETTING_RCLONE_MAPPING,
            SETTING_PLEXMATE_MAX_SCAN_TIME,
            SETTING_PLEXMATE_TIMEOVER_RANGE,
            SETTING_PLEXMATE_PLEX_MAPPING,
            SETTING_STARTUP_EXECUTABLE,
            SETTING_STARTUP_COMMANDS,
            SETTING_STARTUP_TIMEOUT,
            SETTING_STARTUP_DEPENDENCIES,
            SETTING_GDS_TOOL_REQUEST_SPAN,
            SETTING_GDS_TOOL_REQUEST_AUTO,
            SETTING_GDS_TOOL_FP_SPAN,
            SETTING_GDS_TOOL_FP_AUTO,
            SETTING_LOGGING_LOGIN,
            SETTING_LOGGING_ACCESS,
            SETTING_LOGGING_ACCESS_FILE,
            SETTING_LOGGING_ACCESS_FORMAT,
        ]
        for conf in confs:
            args[conf] = CONFIG.get(conf)
        args[SETTING_LOGGING_LOGIN_FILE] = f"{FRAMEWORK.config['path_data']}/log/system.log"
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
        command, query, ids = self.pre_command(request)
        mod = query.get('mod', ['no_mod'])[0]
        span = int(query.get('span', ['-1'])[0])
        GDSToolAider().delete(mod, span)
        return self.returns('success', 'DB 정리를 실행합니다.')

    def command_check_timeover(self, request: flask.Request) -> dict:
        command, query, ids = self.pre_command(request)
        num_range = query.get('range', ['0~0'])[0]
        plexmate = PlexmateAider()
        plexmate.check_timeover(num_range)
        return self.returns('success', 'TIMEOUT 항목을 READY로 변경합니다.')

    def command_default(self, request: flask.Request) -> tuple[bool, str]:
        '''override'''
        return super().command_default(request)

    def setting_save_after(self, changes: list) -> None:
        '''override'''
        super().setting_save_after(changes)
        for change in changes:
            if change == f'{self.name}_startup_dependencies':
                SettingAider.depends(CONFIG.get(SETTING_STARTUP_DEPENDENCIES))
            if change == SETTING_LOGGING_LOGIN:
                enable = CONFIG.get(SETTING_LOGGING_LOGIN)
                SettingAider.set_login_log(enable.lower() == 'true')

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()
        if not CONFIG.get(SETTING_RCLONE_REMOTE_VFSES) and CONFIG.get(SETTING_RCLONE_REMOTE_VFS):
            vfses = RcloneAider().vfs_list()
            CONFIG.set(SETTING_RCLONE_REMOTE_VFSES, '|'.join(vfses))
        if CONFIG.get(SETTING_GDS_TOOL_REQUEST_AUTO).lower() == 'true':
            GDSToolAider().delete('request', CONFIG.get_int(SETTING_GDS_TOOL_REQUEST_SPAN))
        if CONFIG.get(SETTING_GDS_TOOL_FP_AUTO).lower() == 'true':
            GDSToolAider().delete('fp', CONFIG.get_int(SETTING_GDS_TOOL_FP_SPAN))
        if CONFIG.get(SETTING_LOGGING_LOGIN).lower() == 'true':
            SettingAider.set_login_log()

    @FRAMEWORK.app.after_request
    def after_request(response: flask.Response) -> flask.Response:
        enable = CONFIG.get(SETTING_LOGGING_ACCESS).lower() == 'true'
        if enable:
            request = flask.request
            namespace = {
                'remote': SettingAider.get_client_ip(request),
                'method': request.method,
                'scheme': request.scheme,
                'path': request.full_path,
                'status': response.status_code,
                'agent': request.user_agent,
                'length': response.content_length,
            }
            file = CONFIG.get(SETTING_LOGGING_ACCESS_FILE) or f"{FRAMEWORK.config.get('path_data', '/data')}/log/access.log"
            level = FRAMEWORK.SystemModelSetting.get_int('log_level') or logging.DEBUG
            logger = SettingAider.get_rotating_file_logger(file, level=level)
            log_format = CONFIG.get(SETTING_LOGGING_ACCESS_FORMAT)
            if not log_format:
                log_format = '{remote} {method} "{path}" {status}'
                CONFIG.set(SETTING_LOGGING_ACCESS_FORMAT, log_format)
            try:
                logger.log(level, log_format.format(**namespace))
            except:
                LOGGER.exception(f'엑세스 로그 형식 확인: {log_format}')
        return response


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
        confs = [
            SCHEDULE_WORKING_DIRECTORY,
            SCHEDULE_LAST_LIST_OPTION,
            SETTING_RCLONE_REMOTE_VFS,
            SETTING_RCLONE_REMOTE_VFSES,
        ]
        for conf in confs:
            args[conf] = CONFIG.get(conf)
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

    def update_job(self, job_id: int, query: dict[str, list]) -> Job:
        old_job = Job.get_job(job_id)
        job = Job.update_formdata(job_id, query)
        if old_job.id > 0:
            self.reload_schedule(job, old_job)
        return job

    def command_default(self, request: flask.Request) -> tuple[bool, str]:
        '''override'''
        return super().command_default(request)

    def command_list(self, request: flask.Request) -> dict:
        command, query, ids = self.pre_command(request)
        path = query.get('target', ['/'])[0]
        dir_list = json.dumps(BrowserAider.get_dir(path))
        CONFIG.set(SCHEDULE_WORKING_DIRECTORY, path)
        if dir_list:
            return self.returns('success', data=dir_list)
        else:
            return self.returns('warning', '폴더 목록을 생성할 수 없습니다.')

    def command_save(self, request: flask.Request) -> dict:
        command, query, ids = self.pre_command(request)
        if len(ids) > 1:
            query.pop('sch-recursive', None)
            query.pop('sch-schedule-auto-start', None)
            if query:
                for _id in ids:
                    self.update_job(_id, query)
                return self.returns('success', '수정했습니다.')
            else:
                return self.returns('warning', '수정할 항목이 없습니다.')
        else:
            job = self.update_job(ids[0], query)
            if job.id > 0:
                return self.returns('success', '저장했습니다.')
            else:
                return self.returns('warning', '저장할 수 없습니다.')

    def command_delete(self, request: flask.Request) -> dict:
        command, query, ids = self.pre_command(request)
        if len(ids) > 1:
            not_deleted = []
            LOGGER.info(f'to be deleted: {ids}')
            for _id in ids:
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
            if Job.delete_by_id(ids[0]):
                self.set_schedule(ids[0], False)
                return self.returns('success', f'삭제 했습니다: ID {ids[0]}')
            else:
                return self.returns('warning',  f'삭제할 수 없습니다: ID {ids[0]}')

    def command_execute(self, request: flask.Request) -> dict:
        command, query, ids = self.pre_command(request)
        self.run_async(self.start_job, (Job.get_job(ids[0]),))
        return self.returns('success', '일정을 실행했습니다.')

    def command_schedule(self, request: flask.Request) -> dict:
        command, query, ids = self.pre_command(request)
        active = query.get('active', ['false'])[0].lower() == 'true'
        result, msg = self.set_schedule(ids[0], active)
        return self.returns('success' if result else 'warning', msg)

    def command_get_job(self, request: flask.Request) -> dict:
        command, query, ids = self.pre_command(request)
        job = Job.get_by_id(ids[0])
        if job:
            return self.returns('success', data=job.as_dict())
        else:
            return self.returns('warning', f'일정을 찾을 수 없습니다: ID {ids[0]}')


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
            TOOL_TRASH_LAST_LIST_OPTION: ''
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
        command, query, ids = self.pre_command(request)
        section_type = query.get('section_type', ['movie'])[0]
        section_id = int(query.get('section_id', ['-1'])[0])
        page_no = int(query.get('page', ['1'])[0])
        limit = int(query.get('limit', ['30'])[0])
        CONFIG.set(TOOL_TRASH_LAST_LIST_OPTION, f'{section_type}|{section_id}|{page_no}')
        return self.returns('success', data=PlexmateAider().get_trash_list(int(section_id), page_no, limit))

    def command_stop(self, request: flask.Request) -> dict:
        status = CONFIG.get(TOOL_TRASH_TASK_STATUS)
        if status == STATUS_KEYS[1] or status == STATUS_KEYS[3]:
            CONFIG.set(TOOL_TRASH_TASK_STATUS, STATUS_KEYS[3])
            return self.returns('success', '작업을 멈추는 중입니다.')
        else:
            return self.returns('warning', '실행중이 아닙니다.')

    @check_status
    def command_delete(self, request: flask.Request) -> dict:
        command, query, ids = self.pre_command(request)
        metadata_id = int(query.get('metadata_id', ['-1'])[0])
        mediaitem_id = int(query.get('mediaitem_id', ['-1'])[0])
        result, msg = PlexmateAider().delete_media(metadata_id, mediaitem_id)
        return self.returns('success' if result else 'warning', msg)

    @check_status
    def command_default(self, request: flask.Request) -> dict:
        '''override'''
        command, query, ids = self.pre_command(request)
        if command in TOOL_TRASH_KEYS:
            job = Job.get_job()
            job.task = command
            job.section_id = int(query.get('section_id', ['-1'])[0])
            job.vfs = query.get('vfs', ['remote:'])[0]
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
        confs = [
            TOOL_TRASH_TASK_STATUS,
            SETTING_RCLONE_REMOTE_VFS,
            SETTING_RCLONE_REMOTE_VFSES,
            TOOL_TRASH_LAST_LIST_OPTION
        ]
        for conf in confs:
            args[conf] = CONFIG.get(conf)
        return args

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()
        CONFIG.set(TOOL_TRASH_TASK_STATUS, STATUS_KEYS[0])

    def plugin_unload(self) -> None:
        '''override'''
        super().plugin_unload()
        CONFIG.set(TOOL_TRASH_TASK_STATUS, STATUS_KEYS[0])
