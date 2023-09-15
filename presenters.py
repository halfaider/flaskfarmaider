import json
import traceback
from typing import Any
from urllib.parse import parse_qs
from threading import Thread
import sqlite3
import time

from .models import Job
from .aiders import BrowserAider, SettingAider, JobAider, PlexmateAider, GDSToolAider
from .setup import Response, render_template, jsonify, LocalProxy, PluginBase, PluginModuleBase, PluginPageBase, system_plugin, flask_login
from .setup import FRAMEWORK, PLUGIN, LOGGER, CONFIG, default_route_socketio_module
from .constants import SETTING, TASK_KEYS, SCAN_MODE_KEYS, SCHEDULE, SECTION_TYPE_KEYS, STATUSES, README, TOOL, SCHEDULE_DB_VERSIONS, TOOL_LOGIN_LOG_FILE
from .constants import TASKS, STATUS_KEYS, FF_SCHEDULE_KEYS, SCAN_MODES, SECTION_TYPES, FF_SCHEDULES, TOOL_TRASH, MANUAL, TOOL_ETC_SETTING
from .constants import SETTING_DB_VERSION, SETTING_RCLONE_REMOTE_ADDR, SETTING_RCLONE_REMOTE_VFS, SETTING_RCLONE_REMOTE_USER, TOOL_GDS_TOOL_REQUEST_TOTAL
from .constants import SETTING_RCLONE_REMOTE_PASS, SETTING_RCLONE_MAPPING, SETTING_PLEXMATE_MAX_SCAN_TIME, SETTING_PLEXMATE_TIMEOVER_RANGE, TOOL_LOGIN_LOG_ENABLE
from .constants import SETTING_PLEXMATE_PLEX_MAPPING, SETTING_STARTUP_EXECUTABLE, SETTING_STARTUP_COMMANDS, SETTING_STARTUP_TIMEOUT, SETTING_STARTUP_DEPENDENCIES
from .constants import SCHEDULE_WORKING_DIRECTORY, SCHEDULE_LAST_LIST_OPTION, TOOL_TRASH_KEYS, TOOL_TRASHES, TOOL_TRASH_TASK_STATUS, SCHEDULE_DB_VERSION
from .constants import TOOL_GDS_TOOL_REQUEST_SPAN, TOOL_GDS_TOOL_REQUEST_AUTO, TOOL_GDS_TOOL_FP_SPAN, TOOL_GDS_TOOL_FP_AUTO, TOOL_GDS_TOOL_FP_TOTAL
from . import migrations


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

    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        default_route_socketio_module(self)

    def set_recent_menu(self, req: LocalProxy) -> None:
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

    def prerender(self, sub: str, req: LocalProxy) -> None:
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
            self.run_async(JobAider().start_job, (Job.get_job(info=job),))
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

    @FRAMEWORK.celery.task()
    def celery_link(result) -> None:
        pass

    def callback_sio(self, data: dict) -> None:
        self.socketio_callback('result', {'status': data.get('status'), 'data': data.get('result')})


class BaseModule(Base, PluginModuleBase):

    def __init__(self, plugin: PluginBase, first_menu: str = None, name: str = None, scheduler_desc: str = None) -> None:
        '''mod_ins = mod(self) in PluginBase.set_module_list()'''
        super().__init__(plugin, first_menu=first_menu, name=name, scheduler_desc=scheduler_desc)
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

    def process_menu(self, sub: str, req: LocalProxy) -> Response:
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

    def process_ajax(self, sub: str, req: LocalProxy):
        '''override'''
        pass

    def process_command(self, command: str, arg1: str, arg2: str, arg3: str, req: LocalProxy) -> Response:
        '''override'''
        pass

    def process_api(self, sub: str, req: LocalProxy):
        '''override'''
        pass

    def process_normal(self, sub: str, req: LocalProxy):
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


class BasePage(Base, PluginPageBase):

    def __init__(self, plugin: PluginBase, parent: PluginModuleBase, name: str = None, scheduler_desc: str = None) -> None:
        '''mod_ins = mod(self.P, self) in PluginModuleBase.set_page_list()'''
        super().__init__(plugin, parent, name=name, scheduler_desc=scheduler_desc)
        self.db_default = {}

    def process_menu(self, req: LocalProxy) -> Response:
        '''override'''
        self.prerender(self.name, req)
        try:
            args = self.get_template_args()
            return render_template(f'{PLUGIN.package_name}_{self.parent.name}_{self.name}.html', args=args)
        except Exception as e:
            self.P.logger.error(traceback.format_exc())
            return render_template('sample.html', title=f"process_menu() - {PLUGIN.package_name}/{self.parent.name}/{self.name}")

    def process_ajax(self, sub: str, req: LocalProxy):
        '''override'''
        pass

    def process_api(self, sub: str, req: LocalProxy):
        '''override'''
        pass

    def process_normal(self, sub: str, req: LocalProxy):
        '''override'''
        pass

    def process_command(self, command: str, arg1: str, arg2: str, arg3: str, req: LocalProxy) -> Response:
        '''override'''
        pass

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

    def prerender(self, sub: str, req: LocalProxy) -> None:
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

    def process_command(self, command: str, arg1: str, arg2: str, arg3: str, req: LocalProxy) -> Response:
        '''ovverride'''
        ret = {'ret':'success', 'title': 'Rclone Remote'}
        try:
            if command == 'command_test_connection':
                response = SettingAider().remote_command('vfs/list', arg1, arg2, arg3)
                if int(str(response.status_code)[0]) == 2:
                    ret['vfses'] = response.json()['vfses']
                else:
                    ret['ret'] = 'failed'
                ret['modal'] = response.text
            elif command == 'save':
                self.depends()
        except:
            tb = traceback.format_exc()
            LOGGER.error(tb)
            ret['ret'] = 'failed'
            ret['modal'] = str(tb)
        finally:
            return jsonify(ret)

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
                    migrations.migrate(ver, table_jobs, cs)
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

    def process_command(self, command: str, arg1: str | None, arg2: str | None, arg3: str | None, request: LocalProxy) -> Response:
        '''override'''
        LOGGER.debug(f'요청: {command}, {arg1}, {arg2}, {arg3}')
        try:
            # 일정 리스트는 Job.web_list()
            if command == 'list':
                browseraider = BrowserAider()
                dir_list = json.dumps(browseraider.get_dir(arg1))
                CONFIG.set(SCHEDULE_WORKING_DIRECTORY, arg1)
                if dir_list:
                    result, data = True, dir_list
                else:
                    result, data = False, '폴더 목록을 생성할 수 없습니다.'
            elif command == 'save':
                query = parse_qs(arg1)
                old_job = Job.get_job(int(query.get('id')[0]))
                job = Job.update_formdata(query)
                if job.id > 0:
                    def re_add(job):
                        msg = ''
                        schedule_id = JobAider.create_schedule_id(job.id)
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
                                    JobAider.add_schedule(job.id)
                                    msg = f'일정을 재등록 했습니다: {schedule_id}'
                                LOGGER.debug(msg)
                        job = job.as_dict()
                        job['is_include'] = FRAMEWORK.scheduler.is_include(schedule_id)
                        job['msg'] = msg
                        return job
                    if old_job.id > 0:
                        th = ThreadHasReturn(target=re_add, args=(job,), daemon=True, callback=self.callback_sio)
                        th.start()
                    result, data = True, '저장했습니다.'
                else:
                    result, data = False, '저장할 수 없습니다.'
            elif command == 'delete':
                if Job.delete_by_id(arg1):
                    JobAider.set_schedule(int(arg1), False)
                    result, data = True, f'삭제 했습니다: ID {arg1}'
                else:
                    result, data = False, f'삭제할 수 없습니다: ID {arg1}'
            elif command == 'execute':
                self.run_async(JobAider.start_job, (Job.get_job(int(arg1)),))
                result, data = True, '일정을 실행했습니다.'
            elif command == 'schedule':
                active = True if arg2.lower() == 'true' else False
                result, data = JobAider.set_schedule(int(arg1), active)
            elif command in TASK_KEYS:
                result, data = self.task_command(command, arg1, arg2, arg3)
            elif command == 'test':
                result, data = True, '테스트 작업'
            else:
                result, data = False, f'알 수 없는 명령입니다: {command}'
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            result, data = False, str(e)
        finally:
            return jsonify({'success': result, 'data': data})

    def plugin_load(self) -> None:
        '''override'''
        jobs = Job.get_list()
        jobaider = JobAider()
        for job in jobs:
            if job.schedule_mode == FF_SCHEDULE_KEYS[1]:
                self.run_async(JobAider().start_job, (job,))
            elif job.schedule_mode == FF_SCHEDULE_KEYS[2] and job.schedule_auto_start:
                jobaider.add_schedule(job.id)


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

    def process_command(self, command: str, arg1: str | None, arg2: str | None, arg3: str | None, request: LocalProxy) -> Response:
        '''override'''
        LOGGER.debug(f'요청: {command}, {arg1}, {arg2}, {arg3}')
        try:
            status = CONFIG.get(TOOL_TRASH_TASK_STATUS)
            if command == 'status':
                result, data = True, status
            elif command == 'list':
                section_id = int(arg1)
                page_no = int(arg2)
                limit = int(arg3)
                plexmateaider = PlexmateAider()
                result, data = True, plexmateaider.get_trash_list(section_id, page_no, limit)
            elif command == 'stop':
                if status == STATUS_KEYS[1] or status == STATUS_KEYS[3]:
                    CONFIG.set(TOOL_TRASH_TASK_STATUS, STATUS_KEYS[3])
                    result, data = True, "작업을 멈추는 중입니다."
                else:
                    result, data = False, "실행중이 아닙니다."
            elif status == STATUS_KEYS[0]:
                if command == 'delete':
                    metadata_id = int(arg1)
                    mediaitem_id = int(arg2)
                    result, data = True, PlexmateAider().delete_media(metadata_id, mediaitem_id)
                elif command in TASK_KEYS:
                    result, data = self.task_command(command, arg1, arg2, arg3)
                elif command in TOOL_TRASH_KEYS:
                    if status == STATUS_KEYS[0]:
                        job = Job.get_job()
                        job.task = command
                        job.section_id = int(arg1)
                        self.run_async(JobAider().start_job, (job,))
                        result, data = True, f'작업을 실행했습니다.'
                    else:
                        result, data = False, '작업이 실행중입니다.'
                else:
                    result, data = False, f'알 수 없는 명령입니다: {command}'
            else:
                result, data = False, '작업이 실행중입니다.'
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            result, data = False, str(e)
        finally:
            return jsonify({'success': result, 'data': data})


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

    def process_command(self, command: str, arg1: str | None, arg2: str | None, arg3: str | None, request: LocalProxy) -> Response:
        '''override'''
        LOGGER.debug(f'요청: {command}, {arg1}, {arg2}, {arg3}')
        try:
            if command == 'delete':
                mod = arg1
                span = int(arg2)
                GDSToolAider().delete(mod, span)
                result, data = True, f'DB 정리를 실행합니다.'
            else:
                result, data = False, f'알 수 없는 명령입니다: {command}'
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            result, data = False, str(e)
        finally:
            return jsonify({'success': result, 'data': data})

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

    def process_command_route_system(self, command: str, arg1: str | None, arg2: str | None, arg3: str | None, request: LocalProxy) -> Response:
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
