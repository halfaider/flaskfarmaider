import json
import traceback
from typing import Any
from urllib.parse import parse_qs
from threading import Thread
import sqlite3
import time
import functools

from flask import Response, render_template, jsonify
from flask.wrappers import Request
import flask_login

from .setup import PluginBase, PluginModuleBase, PluginPageBase, system_plugin, default_route_socketio_module, ModelBase, FrameworkJob
from .setup import FRAMEWORK, PLUGIN, LOGGER, CONFIG
from .models import Job
from .aiders import BrowserAider, SettingAider, JobAider, PlexmateAider, GDSToolAider
from .migrations import migrate
from .constants import *


class ThreadHasReturn(Thread):

    def __init__(self, group=None, target: callable = None, name: str = None, args: tuple | list = (), kwargs: dict = {}, daemon: bool = None, callback: callable = None):
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


class Base():

    def __init__(self) -> None:
        default_route_socketio_module(self)
        self.commands = {
            'default': self.command_default,
        }

    def set_recent_menu(self, req: Request) -> None:
        current_menu = '|'.join(req.path[1:].split('/')[1:])
        if not current_menu == CONFIG.get('recent_menu_plugin'):
            CONFIG.set('recent_menu_plugin', current_menu)

    def get_template_args(self) -> dict[str, Any]:
        args = {
            'package_name': PLUGIN.package_name,
            'module_name': self.name if isinstance(self, BaseModule) else self.parent.name,
            'page_name': self.name if isinstance(self, BasePage) else None,
        }
        return args

    def prerender(self, sub: str, req: Request) -> None:
        self.set_recent_menu(req)

    def task_command(self, task: str, target: str, recursive: str, scan: str) -> tuple[bool, str]:
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
            }
            self.run_async(self.start_job, (Job.get_job(info=job),))
            result, msg = True, '작업을 실행했습니다.'
        else:
            result, msg = False, '경로 정보가 없습니다.'
        return result, msg

    def run_async(self, func: callable, args: tuple = (), kwargs: dict = {}, **opts) -> None:
        from .setup import CELERY_ACTIVE
        if CELERY_ACTIVE:
            result = func.apply_async(args=args, kwargs=kwargs, link=self.celery_link.s(), **opts)
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

    def process_command(self, command: str, arg1: str, arg2: str, arg3: str, request: Request) -> Response:
        try:
            data = self.commands.get(command, self.commands.get('default'))(request)
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            data = self.returns('warning', str(e))
        finally:
            return jsonify(data)

    def command_default(self, request: Request) -> dict:
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


class BaseModule(PluginModuleBase, Base):

    def __init__(self, plugin: PluginBase, first_menu: str = None, name: str = None, scheduler_desc: str = None) -> None:
        '''mod_ins = mod(self) in PluginBase.set_module_list()'''
        PluginModuleBase.__init__(self, plugin, first_menu=first_menu, name=name, scheduler_desc=scheduler_desc)
        Base.__init__(self)
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

    def process_menu(self, sub: str, req: Request) -> Response:
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
                return render_template(f'{PLUGIN.package_name}_{self.name}.html', args=args)
        except:
            LOGGER.error(traceback.format_exc())
            return render_template('sample.html', title=f"process_menu() - {PLUGIN.package_name}/{self.name}/{sub}")

    def process_ajax(self, sub: str, req: Request):
        '''override'''
        pass

    def process_command(self, command: str, arg1: str, arg2: str, arg3: str, req: Request) -> Response:
        '''override'''
        return Base.process_command(self, command, arg1, arg2, arg3, req)

    def process_api(self, sub: str, req: Request):
        '''override'''
        pass

    def process_normal(self, sub: str, req: Request):
        '''override'''
        pass

    def scheduler_function(self):
        '''override'''
        pass

    def db_delete(self, day: int | str) -> int:
        '''override'''
        return super().db_delete(day)

    def plugin_load(self):
        '''override'''
        pass

    def plugin_load_celery(self):
        '''override'''
        pass

    def plugin_unload(self):
        '''override'''
        pass

    def setting_save_after(self, change_list: list) -> None:
        '''override'''
        pass

    def process_telegram_data(self, data, target=None):
        '''override'''
        pass

    def migration(self):
        '''override'''
        pass

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

    def socketio_connect(self):
        '''override'''
        pass

    def socketio_disconnect(self):
        '''override'''
        pass

    def arg_to_dict(self, arg):
        '''override'''
        return super().arg_to_dict(arg)

    def get_scheduler_name(self):
        '''override'''
        return super().get_scheduler_name()

    def process_discord_data(self, data):
        '''override'''
        pass

    def start_celery(self, func: callable, *args, on_message: callable = None, page: PluginPageBase = None) -> Any:
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


class BasePage(PluginPageBase, Base):

    def __init__(self, plugin: PluginBase, parent: PluginModuleBase, name: str = None, scheduler_desc: str = None) -> None:
        '''mod_ins = mod(self.P, self) in PluginModuleBase.set_page_list()'''
        PluginPageBase.__init__(self, plugin, parent, name=name, scheduler_desc=scheduler_desc)
        Base.__init__(self)
        self.db_default = {}

    def process_menu(self, req: Request) -> Response:
        '''override'''
        self.prerender(self.name, req)
        try:
            args = self.get_template_args()
            return render_template(f'{PLUGIN.package_name}_{self.parent.name}_{self.name}.html', args=args)
        except:
            self.P.logger.error(traceback.format_exc())
            return render_template('sample.html', title=f"process_menu() - {PLUGIN.package_name}/{self.parent.name}/{self.name}")

    def process_ajax(self, sub: str, req: Request):
        '''override'''
        pass

    def process_api(self, sub: str, req: Request):
        '''override'''
        pass

    def process_normal(self, sub: str, req: Request):
        '''override'''
        pass

    def process_command(self, command: str, arg1: str, arg2: str, arg3: str, req: Request) -> Response:
        '''override'''
        return Base.process_command(self, command, arg1, arg2, arg3, req)

    def plugin_load(self):
        '''override'''
        pass

    def plugin_load_celery(self):
        '''override'''
        pass

    def plugin_unload(self):
        '''override'''
        pass

    def scheduler_function(self):
        '''override'''
        pass

    def get_scheduler_desc(self) -> str:
        '''override'''
        return super().get_scheduler_desc()

    def get_scheduler_interval(self) -> str:
        '''override'''
        return super().get_scheduler_interval()

    def get_scheduler_name(self) -> str:
        '''override'''
        return super().get_scheduler_name()

    def migration(self):
        '''override'''
        pass

    def setting_save_after(self, change_list: list) -> None:
        '''override'''
        pass

    def process_telegram_data(self, data, target=None):
        '''override'''
        pass

    def arg_to_dict(self, arg) -> dict:
        '''override'''
        return super().arg_to_dict(arg)

    def get_page(self, page_name) -> PluginPageBase:
        '''override'''
        return super().get_page(page_name)

    def get_module(self, module_name) -> PluginModuleBase:
        '''override'''
        return super().get_module(module_name)

    def process_discord_data(self, data):
        '''override'''
        pass

    def db_delete(self, day: int | str) -> int:
        '''override'''
        return super().db_delete(day)

    def start_celery(self, func: callable, *args, on_message: callable = None) -> Any:
        '''override'''
        return self.parent.start_celery(func, *args, on_message, page=self)


class Setting(BaseModule):

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name=SETTING)
        self.db_default = {
            SETTING_DB_VERSION: '',
            SETTING_RCLONE_REMOTE_ADDR: 'http://172.17.0.1:5572',
            SETTING_RCLONE_REMOTE_VFS: '',
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
        }
        self.commands.update({'command_test_connection': self.command_test_conn})

    def prerender(self, sub: str, req: Request) -> None:
        '''override'''
        super().prerender(sub, req)
        # yaml 파일 우선
        CONFIG.set(SETTING_STARTUP_DEPENDENCIES, SettingAider().depends())

    def get_template_args(self) -> dict[str, Any]:
        '''override'''
        args = super().get_template_args()
        args[SETTING_RCLONE_REMOTE_ADDR] = CONFIG.get(SETTING_RCLONE_REMOTE_ADDR)
        args[SETTING_RCLONE_REMOTE_VFS] = CONFIG.get(SETTING_RCLONE_REMOTE_VFS)
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
        return args

    def command_test_conn(self, request: Request) -> dict:
        response = SettingAider().remote_command('vfs/list', request.form.get('arg1'), request.form.get('arg2'), request.form.get('arg3'))
        data = {'title': 'Rclone Remote', 'modal': response.text}
        if int(str(response.status_code)[0]) == 2:
            data['ret'] = 'success'
            data['msg'] = '접속에 성공했습니다.'
            data['vfses'] = response.json()['vfses']
        else:
            data['ret'] = 'warning'
            data['msg'] = '접속에 실패했습니다.'
        return data

    def command_default(self, request: Request) -> tuple[bool, str]:
        '''override'''
        return super().command_default(request)

    def setting_save_after(self, changes: list) -> None:
        '''override'''
        for change in changes:
            if change == f'{self.name}_startup_dependencies':
                SettingAider().depends(CONFIG.get(SETTING_STARTUP_DEPENDENCIES))


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
            }
        )

    def migration(self):
        '''override'''
        with FRAMEWORK.app.app_context():
            set_db_ver = CONFIG.get(SETTING_DB_VERSION)
            if set_db_ver:
                current_db_ver = CONFIG.get(SETTING_DB_VERSION)
            else:
                current_db_ver = CONFIG.get(SCHEDULE_DB_VERSION)
            db_file = FRAMEWORK.app.config['SQLALCHEMY_BINDS'][PLUGIN.package_name].replace('sqlite:///', '').split('?')[0]
            LOGGER.debug(f'DB 버전: {current_db_ver}')
            with sqlite3.connect(db_file) as conn:
                conn.row_factory = sqlite3.Row
                cs = conn.cursor()
                table_jobs = f'{PLUGIN.package_name}_jobs'
                # DB 볼륨 정리
                cs.execute(f'VACUUM;').fetchall()
                for ver in SCHEDULE_DB_VERSIONS[(SCHEDULE_DB_VERSIONS.index(current_db_ver)):]:
                    migrate(ver, table_jobs, cs)
                    current_db_ver = ver
                conn.commit()
                FRAMEWORK.db.session.flush()
            LOGGER.debug(f'최종 DB 버전: {current_db_ver}')
            CONFIG.set(SCHEDULE_DB_VERSION, current_db_ver)
            CONFIG.set(SETTING_DB_VERSION, '')

    def get_template_args(self) -> dict[str, Any]:
        '''override'''
        args = super().get_template_args()
        args[f'{self.name}_working_directory'] = CONFIG.get(SCHEDULE_WORKING_DIRECTORY)
        args[f'{self.name}_last_list_option'] = CONFIG.get(SCHEDULE_LAST_LIST_OPTION)
        args['rclone_remote_vfs'] = CONFIG.get(SETTING_RCLONE_REMOTE_VFS)
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
        return args

    def plugin_load(self) -> None:
        '''override'''
        jobs = Job.get_list()
        for job in jobs:
            if job.schedule_mode == FF_SCHEDULE_KEYS[1]:
                self.run_async(self.start_job, (job,))
            elif job.schedule_mode == FF_SCHEDULE_KEYS[2] and job.schedule_auto_start:
                self.add_schedule(job.id)

    def command_list(self, request: Request) -> dict:
        path = request.form.get('arg1')
        dir_list = json.dumps(BrowserAider().get_dir(path))
        CONFIG.set(SCHEDULE_WORKING_DIRECTORY, path)
        if dir_list:
            return self.returns('success', data=dir_list)
        else:
            return self.returns('warning', '폴더 목록을 생성할 수 없습니다.')

    def command_save(self, request: Request) -> dict:
        query = parse_qs(request.form.get('arg1'))
        old_job = Job.get_job(int(query.get('id')[0]))
        job = Job.update_formdata(query)
        if old_job.id > 0:
            th = ThreadHasReturn(target=self.schedule_reload, args=(job, old_job), daemon=True, callback=self.callback_sio)
            th.start()
            return self.returns('success', '저장했습니다.')
        else:
            return self.returns('warning', '저장할 수 없습니다.')

    def command_delete(self, request: Request) -> dict:
        job_id = int(request.form.get('arg1'))
        if Job.delete_by_id(job_id):
            self.set_schedule(job_id, False)
            return self.returns('success', f'삭제 했습니다: ID {job_id}')
        else:
            return self.returns('warning',  f'삭제할 수 없습니다: ID {job_id}')

    def command_execute(self, request: Request) -> dict:
        job_id = int(request.form.get('arg1'))
        self.run_async(self.start_job, (Job.get_job(job_id),))
        return self.returns('success', '일정을 실행했습니다.')

    def command_schedule(self, request: Request) -> dict:
        job_id = int(request.form.get('arg1'))
        active = True if request.form.get('arg2').lower() == 'true' else False
        result, msg = self.set_schedule(job_id, active)
        return self.returns('success' if result else 'warning', msg)


class Manual(BaseModule):

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name=MANUAL)

    def get_template_args(self) -> dict[str, Any]:
        '''override'''
        args = super().get_template_args()
        with README.open(encoding='utf-8', newline='\n') as file:
            manual = file.read()
        args['manual'] = manual
        return args


class Tool(BaseModule):

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name=TOOL, first_menu=TOOL_TRASH)
        self.set_page_list([ToolTrash, ToolEtcSetting])

    def setting_save_after(self, changes: list) -> None:
        '''override'''
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

    def check_status(func: callable):
        @functools.wraps(func)
        def wrap(*args, **kwds) -> dict:
            status = CONFIG.get(TOOL_TRASH_TASK_STATUS)
            if status == STATUS_KEYS[0]:
                return func(*args, **kwds)
            else:
                return {'ret': 'warning', 'msg': '작업이 실행중입니다.'}
        return wrap

    def command_status(self, request: Request) -> dict:
        return self.returns('success', data={'status': CONFIG.get(TOOL_TRASH_TASK_STATUS)})

    def command_list(self, request: Request) -> dict:
        section_id = int(request.form.get('arg1'))
        page_no = int(request.form.get('arg2'))
        limit = int(request.form.get('arg3'))
        return self.returns('success', data=PlexmateAider().get_trash_list(section_id, page_no, limit))

    def command_stop(self, request: Request) -> dict:
        status = CONFIG.get(TOOL_TRASH_TASK_STATUS)
        if status == STATUS_KEYS[1] or status == STATUS_KEYS[3]:
            CONFIG.set(TOOL_TRASH_TASK_STATUS, STATUS_KEYS[3])
            return self.returns('success', '작업을 멈추는 중입니다.')
        else:
            return self.returns('warning', '실행중이 아닙니다.')

    @check_status
    def command_delete(self, request: Request) -> dict:
        metadata_id = int(request.form.get('arg1'))
        mediaitem_id = int(request.form.get('arg2'))
        result, msg = PlexmateAider().delete_media(metadata_id, mediaitem_id)
        return self.returns('success' if result else 'warning', msg)

    @check_status
    def command_default(self, request: Request) -> dict:
        '''override'''
        command = request.form.get('command')
        if command in TOOL_TRASH_KEYS:
            job = Job.get_job()
            job.task = command
            job.section_id = int(request.form.get('arg1'))
            self.run_async(self.start_job, (job,))
            return self.returns('success', f'작업을 실행했습니다.')
        else:
            return super().command_default(request)

    def get_template_args(self) -> dict[str, Any]:
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
        return args


class ToolEtcSetting(BasePage):

    def __init__(self, plugin: PluginBase, parent: PluginModuleBase) -> None:
        super().__init__(plugin, parent, name=TOOL_ETC_SETTING)
        self.db_default = {
            TOOL_GDS_TOOL_REQUEST_SPAN: '30',
            TOOL_GDS_TOOL_REQUEST_AUTO: 'false',
            TOOL_GDS_TOOL_FP_SPAN: '30',
            TOOL_GDS_TOOL_FP_AUTO: 'false',
            TOOL_LOGIN_LOG_ENABLE: 'false',
        }
        self.system_route = system_plugin.logic.get_module('route')
        self.system_route_process_command = self.system_route.process_command
        self.commands['delete'] = self.command_delete

    def get_template_args(self) -> dict[str, Any]:
        '''override'''
        args = super().get_template_args()
        args[TOOL_GDS_TOOL_REQUEST_SPAN] = CONFIG.get(TOOL_GDS_TOOL_REQUEST_SPAN)
        args[TOOL_GDS_TOOL_REQUEST_AUTO] = CONFIG.get(TOOL_GDS_TOOL_REQUEST_AUTO)
        args[TOOL_GDS_TOOL_FP_SPAN] = CONFIG.get(TOOL_GDS_TOOL_FP_SPAN)
        args[TOOL_GDS_TOOL_FP_AUTO] = CONFIG.get(TOOL_GDS_TOOL_FP_AUTO)
        args[TOOL_LOGIN_LOG_ENABLE] = CONFIG.get(TOOL_LOGIN_LOG_ENABLE).lower()
        args[TOOL_LOGIN_LOG_FILE] = f"{FRAMEWORK.config['path_data']}/log/{system_plugin.package_name}.log"
        try:
            gdsaider = GDSToolAider()
            args[TOOL_GDS_TOOL_REQUEST_TOTAL] = gdsaider.get_total_records('request')
            args[TOOL_GDS_TOOL_FP_TOTAL] = gdsaider.get_total_records('fp')
        except:
            LOGGER.error(traceback.format_exc())
            args[TOOL_GDS_TOOL_REQUEST_TOTAL] = -1
            args[TOOL_GDS_TOOL_FP_TOTAL] = -1
        return args

    def command_delete(self, request: Request) -> dict:
        mod = request.form.get('arg1')
        span = int(request.form.get('arg2'))
        GDSToolAider().delete(mod, span)
        return self.returns('success', 'DB 정리를 실행합니다.')

    def plugin_load(self):
        '''override'''
        request_auto = True if CONFIG.get(TOOL_GDS_TOOL_REQUEST_AUTO).lower() == 'true' else False
        fp_auto = True if CONFIG.get(TOOL_GDS_TOOL_FP_AUTO).lower() == 'true' else False
        gdsaider = GDSToolAider()
        if request_auto:
            gdsaider.delete('request', CONFIG.get_int(TOOL_GDS_TOOL_REQUEST_SPAN))
        if fp_auto:
            gdsaider.delete('fp', CONFIG.get_int(TOOL_GDS_TOOL_FP_SPAN))
        if CONFIG.get(TOOL_LOGIN_LOG_ENABLE).lower() == 'true':
            self.system_route.process_command = self.process_command_route_system

    def setting_save_after(self, changes: list) -> None:
        '''override'''
        for change in changes:
            if change == TOOL_LOGIN_LOG_ENABLE:
                enable = CONFIG.get(TOOL_LOGIN_LOG_ENABLE)
                if enable.lower() == 'true':
                    self.system_route.process_command = self.process_command_route_system
                else:
                    self.system_route.process_command = self.system_route_process_command

    def process_command_route_system(self, command: str, arg1: str | None, arg2: str | None, arg3: str | None, request: Request) -> Response:
        '''alternative of system.route.process_command()'''
        if command == 'login':
            username = arg1
            password = arg2
            remember = (arg3 == 'true')
            client_info = f"user={username} ip={request.environ.get('HTTP_X_REAL_IP') or request.environ.get('HTTP_X_FORWARDED_FOR') or request.remote_addr}"
            failed_msg = f'로그인 실패: {client_info}'
            if username not in FRAMEWORK.users:
                system_plugin.logger.warning(failed_msg)
                return jsonify('no_id')
            elif not FRAMEWORK.users[username].can_login(password):
                system_plugin.logger.warning(failed_msg)
                return jsonify('wrong_password')
            else:
                system_plugin.logger.info(f'로그인 성공: {client_info}')
                FRAMEWORK.users[username].authenticated = True
                flask_login.login_user(FRAMEWORK.users[username], remember=remember)
                return jsonify('redirect')
