import json
import traceback
import urllib.parse
import functools
import logging
import pathlib
import time

import flask

from .setup import PluginBase, PluginModuleBase, ModelBase, FrameworkJob
from .setup import FRAMEWORK, PLUGIN, LOGGER, CONFIG
from .models import Job
from .aiders import JobAider, BrowserAider, SettingAider, PlexmateAider, GDSToolAider, RcloneAider
from .migrations import migrate_schedule, migrate_setting
from .api import BaseModule, BasePage
from .util import ThreadHasReturn, get_rotating_file_logger
from .constants import (TASK_KEYS, TASKS, TOOL_TRASH_KEYS, TOOL_TRASHES, STATUS_KEYS, STATUSES,
    FF_SCHEDULE_KEYS, FF_SCHEDULES, SCAN_MODE_KEYS, SCAN_MODES, SECTION_TYPE_KEYS, SECTION_TYPES,
    SEARCH_KEYS, SEARCHES)


class Setting(BaseModule):

    __DB_VERSIONS = ['1', '2']

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name='setting')
        self.db_default = {
            f'{self.name}_db_version': self.__DB_VERSIONS[-1],
            f'{self.name}_rclone_remote_addr': 'http://172.17.0.1:5275',
            f'{self.name}_rclone_remote_vfs': '',
            f'{self.name}_rclone_remote_vfses': '',
            f'{self.name}_rclone_remote_user': '',
            f'{self.name}_rclone_remote_pass': '',
            f'{self.name}_rclone_remote_mapping': '/mnt/gds:\n/home/cloud/sjva/VOD:/VOD',
            f'{self.name}_plexmate_max_scan_time': '60',
            f'{self.name}_plexmate_timeover_range': '0~0',
            f'{self.name}_plexmate_plex_mapping': '',
            f'{self.name}_startup_executable': 'false',
            f'{self.name}_startup_commands': 'apt-get update',
            f'{self.name}_startup_timeout': '300',
            f'{self.name}_startup_dependencies': SettingAider.depends(),
            f'{self.name}_gds_tool_request_span': '30',
            f'{self.name}_gds_tool_request_auto': 'false',
            f'{self.name}_gds_tool_fp_span': '30',
            f'{self.name}_gds_tool_fp_auto': 'false',
            f'{self.name}_logging_login': 'false',
            f'{self.name}_logging_access': 'false',
            f'{self.name}_logging_access_file': '/data/log/access.log',
            f'{self.name}_logging_access_format': '{remote} {method} "{path}" {status}',
            f'{self.name}_rclone_path_test': 'true',
        }
        self.commands.update({'command_test_connection': self.command_test_conn})
        self.commands['clear_db'] = self.command_clear_db
        self.commands['check_timeover'] = self.command_check_timeover

    def prerender(self, sub: str, req: flask.Request) -> None:
        '''override'''
        super().prerender(sub, req)
        # yaml 파일 우선
        CONFIG.set(f'{self.name}_startup_dependencies', SettingAider.depends())

    def get_template_args(self) -> dict:
        '''override'''
        args = super().get_template_args()
        for conf in self.db_default.keys():
            args[conf] = CONFIG.get(conf)
        args[f'{self.name}_logging_login_file'] = f"{FRAMEWORK.config['path_data']}/log/system.log"
        try:
            gdsaider = GDSToolAider()
            args[f'{self.name}_gds_tool_request_total'] = gdsaider.get_total_records('request')
            args[f'{self.name}_gds_tool_fp_total'] = gdsaider.get_total_records('fp')
        except:
            LOGGER.error(traceback.format_exc())
            args[f'{self.name}_gds_tool_request_total'] = -1
            args[f'{self.name}_gds_tool_fp_total'] = -1
        return args

    def migration(self) -> None:
        '''override'''
        super().migration()
        version = CONFIG.get(f'{self.name}_db_version') or self.__DB_VERSIONS[0]
        version = self._migration(version, self.__DB_VERSIONS, f'{PLUGIN.package_name}_setting', migrate_setting)
        CONFIG.set(f'{self.name}_db_version', version)

    def command_test_conn(self, request: flask.Request) -> dict:
        response = RcloneAider()._vfs_list()
        data = self.returns('success', title='Rclone Remote', modal=response.text)
        if int(str(response.status_code)[0]) == 2:
            data['ret'] = 'success'
            data['msg'] = '접속에 성공했습니다.'
            vfses = sorted(response.json()['vfses'])
            CONFIG.set(f'{self.name}_rclone_remote_vfses', '|'.join(vfses))
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

    def setting_save_after(self, changes: list) -> None:
        '''override'''
        super().setting_save_after(changes)
        for change in changes:
            match change:
                case 'setting_startup_dependencies':
                    SettingAider.depends(CONFIG.get(f'setting_startup_dependencies'))
                case 'setting_logging_login':
                    enable = CONFIG.get(f'setting_logging_login')
                    SettingAider.set_login_log(enable.lower() == 'true')

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()
        if not CONFIG.get(f'{self.name}_rclone_remote_vfses') and CONFIG.get(f'{self.name}_rclone_remote_vfs'):
            vfses = RcloneAider().vfs_list()
            CONFIG.set(f'{self.name}_rclone_remote_vfses', '|'.join(vfses))
        if CONFIG.get(f'{self.name}_gds_tool_request_auto').lower() == 'true':
            GDSToolAider().delete('request', CONFIG.get_int(f'{self.name}_gds_tool_request_span'))
        if CONFIG.get(f'{self.name}_gds_tool_fp_auto').lower() == 'true':
            GDSToolAider().delete('fp', CONFIG.get_int(f'{self.name}_gds_tool_fp_span'))
        if CONFIG.get(f'{self.name}_logging_login').lower() == 'true':
            SettingAider.set_login_log()


class Schedule(BaseModule):

    __DB_VERSIONS = ['1', '2', '3', '4', '5', '6']

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name='schedule')
        self.db_default = {
            f'{self.name}_db_version': self.__DB_VERSIONS[-1],
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
        version = CONFIG.get(f'{self.name}_db_version')
        version = self._migration(version, self.__DB_VERSIONS, f'{PLUGIN.package_name}_jobs', migrate_schedule)
        CONFIG.set(f'{self.name}_db_version', version)

    def get_template_args(self) -> dict:
        '''override'''
        args = super().get_template_args()
        confs = [
            f'{self.name}_working_directory',
            f'{self.name}_last_list_option',
            'setting_rclone_remote_vfs',
            'setting_rclone_remote_vfses',
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
        match active, is_include:
            case True, True:
                result, msg = False, f'이미 일정에 등록되어 있습니다.'
            case False, True:
                result, msg = FRAMEWORK.scheduler.remove_job(schedule_id), '일정에서 제외했습니다.'
            case False, False:
                result, msg = False, '등록되지 않은 일정입니다.'
            case True, False if schedule_mode == FF_SCHEDULE_KEYS[2]:
                result = self.add_schedule(job_id)
                msg = '일정에 등록했습니다.' if result else '일정에 등록하지 못했어요.'
            case _:
                result, msg = False, '등록할 수 없는 일정 방식입니다.'
        return result, msg

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

    def create_schedule_id(self, job_id: int, middle: str = 'schedule') -> str:
        return f'{PLUGIN.package_name}_{middle}_{job_id}'

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()
        for job in Job.get_list():
            if job.schedule_mode == FF_SCHEDULE_KEYS[1]:
                self.run_async(start_job, (job,))
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
        command, query, ids = self.pre_command(request)
        if command in TASK_KEYS:
            result, msg = self.task_command(command, query)
        else:
            result, msg = False, f'알 수 없는 명령입니다: {command}'
        return self.returns('success' if result else 'warning', msg)

    def task_command(self, task: str, query: dict[str, list]) -> tuple[bool, str]:
        '''override'''
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

    def command_list(self, request: flask.Request) -> dict:
        command, query, ids = self.pre_command(request)
        path = query.get('target', ['/'])[0]
        dir_list = json.dumps(BrowserAider.get_dir(path))
        CONFIG.set(f'{self.name}_working_directory', path)
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
        self.run_async(start_job, (Job.get_job(ids[0]),))
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

    readme_file = pathlib.Path(__file__).parent / 'README.md'

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name='manual')

    def get_template_args(self) -> dict:
        '''override'''
        args = super().get_template_args()
        with self.readme_file.open(encoding='utf-8', newline='\n') as file:
            manual = file.read()
        args['manual'] = manual
        return args


class Tool(BaseModule):

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name='tool', first_menu='trash')
        self.set_page_list([ToolTrash])

    def setting_save_after(self, changes: list) -> None:
        '''override'''
        super().setting_save_after(changes)
        for page in self.page_list:
            page.setting_save_after(changes)


class ToolTrash(BasePage):

    def __init__(self, plugin: PluginBase, parent: PluginModuleBase) -> None:
        super().__init__(plugin, parent, name='trash')
        self.db_default = {
            'tool_trash_task_status': STATUS_KEYS[0],
            'tool_trash_last_list_option': ''
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
            status = CONFIG.get('tool_trash_task_status')
            if status == STATUS_KEYS[0]:
                return func(*args, **kwds)
            else:
                return {'ret': 'warning', 'msg': '작업이 실행중입니다.'}
        return wrap

    def command_status(self, request: flask.Request) -> dict:
        return self.returns('success', data={'status': CONFIG.get('tool_trash_task_status')})

    def command_list(self, request: flask.Request) -> dict:
        command, query, ids = self.pre_command(request)
        section_type = query.get('section_type', ['movie'])[0]
        section_id = int(query.get('section_id', ['-1'])[0])
        page_no = int(query.get('page', ['1'])[0])
        limit = int(query.get('limit', ['30'])[0])
        CONFIG.set('tool_trash_last_list_option', f'{section_type}|{section_id}|{page_no}')
        return self.returns('success', data=PlexmateAider().get_trash_list(int(section_id), page_no, limit))

    def command_stop(self, request: flask.Request) -> dict:
        status = CONFIG.get('tool_trash_task_status')
        if status == STATUS_KEYS[1] or status == STATUS_KEYS[3]:
            CONFIG.set('tool_trash_task_status', STATUS_KEYS[3])
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
            self.run_async(start_job, (job,))
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
            'tool_trash_task_status',
            'setting_rclone_remote_vfs',
            'setting_rclone_remote_vfses',
            'tool_trash_last_list_option'
        ]
        for conf in confs:
            args[conf] = CONFIG.get(conf)
        return args

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()
        CONFIG.set('tool_trash_task_status', STATUS_KEYS[0])

    def plugin_unload(self) -> None:
        '''override'''
        super().plugin_unload()
        CONFIG.set('tool_trash_task_status', STATUS_KEYS[0])


@FRAMEWORK.celery.task(bind=True)
def start_job(task, job: ModelBase) -> dict:
    try:
        if job.id and job.id > 0:
            job.set_status(STATUS_KEYS[1])
        if job.task in TOOL_TRASH_KEYS:
            CONFIG.set('tool_trash_task_status', STATUS_KEYS[1])
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
            CONFIG.set('tool_trash_task_status', STATUS_KEYS[0])
        job = job.as_dict()
        job['msg'] = msg
        return job


@FRAMEWORK.app.after_request
def after_request(response: flask.Response) -> flask.Response:
    enable = CONFIG.get('setting_logging_access').lower() == 'true'
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
            'form': urllib.parse.urlencode(request.form, doseq=False),
            'headers': request.headers,
            'hostname': urllib.parse.urlparse(request.base_url).hostname,
        }
        file = CONFIG.get('setting_logging_access_file') or f"{FRAMEWORK.config.get('path_data', '/data')}/log/access.log"
        level = FRAMEWORK.SystemModelSetting.get_int('log_level') or logging.DEBUG
        logger = get_rotating_file_logger(file, level=level)
        log_format = CONFIG.get(f'setting_logging_access_format')
        if not log_format:
            log_format = '{remote} {method} "{path}" {status}'
            CONFIG.set('setting_logging_access_format', log_format)
        try:
            logger.log(level, log_format.format(**namespace))
        except:
            LOGGER.exception(f'엑세스 로그 형식 확인: {log_format}')
    return response
