import json
import traceback
import functools
import pathlib
import time
import datetime
import os

import flask
import google_auth_oauthlib.flow

from .setup import (PluginBase, FrameworkJob,
    FRAMEWORK, PLUGIN, LOGGER, CONFIG,
    set_login_log)
from .models import ScheduleModel
from .aiders import ScheduleAider, SettingAider, PlexmateAider, RcloneAider
from .migrations import migrate_schedule, migrate_setting
from .api import ModuleBase, PageBase
from .util import ThreadHasReturn, get_dir
from .constants import (TASK_KEYS, TASKS, TOOL_TRASH_KEYS, TOOL_TRASHES, STATUS_KEYS, STATUSES,
    FF_SCHEDULE_KEYS, FF_SCHEDULES, SCAN_MODE_KEYS, SCAN_MODES, SECTION_TYPE_KEYS, SECTION_TYPES,
    SEARCH_KEYS, SEARCHES)


class Setting(ModuleBase):

    _DB_VERSIONS = ['1', '2', '3']

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name='setting')
        self.db_default = {
            'setting_db_version': self._DB_VERSIONS[-1],
            'setting_plexmate_max_scan_time': '60',
            'setting_plexmate_timeover_range': '0~0',
            'setting_plexmate_periodic_scan': 'false',
            'setting_plex_mappings': '[""]',
            'setting_startup_executable': 'false',
            'setting_startup_commands': '[""]',
            'setting_startup_timeout': '300',
            'setting_logging_login': 'false',
            'setting_logging_access': 'false',
            'setting_logging_access_file': '/data/log/access.log',
            'setting_logging_access_format': '{remote} {method} "{path}" {status}',
            'setting_general_timeout': '0',
            'setting_rclone_remotes': '[""]',
            'setting_rclone_mappings': '[""]',
            'setting_config_file': f'{FRAMEWORK.config["path_data"]}/db/{__package__}.yaml',
            'setting_logging_access_regex': '',
        }

    def get_template_args(self) -> dict:
        '''override'''
        args = super().get_template_args()
        for conf in self.db_default.keys():
            if conf in ['setting_rclone_remotes', 'setting_rclone_mappings', 'setting_plex_mappings', 'setting_startup_commands']:
                args[conf] = CONFIG.get_json(conf)
            else:
                args[conf] = CONFIG.get(conf)
        args['setting_logging_login_file'] = f"{FRAMEWORK.config['path_data']}/log/system.log"
        args['setting_config_file_content'] = SettingAider.config_from_file() or ''
        return args

    def migration(self) -> None:
        '''override'''
        super().migration()
        self._migration('setting_db_version', f'{PLUGIN.package_name}_setting', migrate_setting)

    def command_test_connection(self, request: flask.Request) -> dict:
        rclone = RcloneAider(request.form.get('arg1'))
        result = rclone.vfs__list()
        try:
            data = self.returns('success', title=request.form.get('arg1'), modal=json.dumps(result))
        except:
            LOGGER.error(traceback.format_exc())
            LOGGER.error(f'Invalid JSON: {result}')
            data = self.returns('success', title=request.form.get('arg1'), modal=result)
        if 'status_code' in result:
            data['ret'] = 'danger'
            data['msg'] = '접속에 실패했습니다.'
        else:
            data['msg'] = '접속에 성공했습니다.'
        return data

    def command_save(self, request: flask.Request) -> dict:
        parsed = self.parse_command(request)
        changes = []
        result = self.returns('success', msg='설정을 저장했습니다.')
        LOGGER.debug(f'Form data: {parsed["query"]}')
        try:
            for key in parsed['query'].keys():
                match key:
                    case 'checkbox-helper':
                        continue
                    case 'setting_rclone_remotes' | 'setting_rclone_mappings' | 'setting_plex_mappings' | 'setting_startup_commands':
                        values = [v.strip() for v in parsed['query'][key]]
                        if not CONFIG.set_json(key, values):
                            continue
                    case 'setting_logging_access' | 'setting_startup_executable' | 'setting_logging_login' | 'setting_plexmate_periodic_scan':
                        if parsed['query'][key][0].strip().lower() in ['true', 'on', 'yes']:
                            CONFIG.set(key, 'true')
                        else:
                            CONFIG.set(key, 'false')
                    case _:
                        value = parsed['query'][key][0].strip()
                        CONFIG.set(key, value)
                changes.append(key)
            if changes:
                self.setting_save_after(changes)
        except:
            LOGGER.error(traceback.format_exc())
            result['ret'] = 'warning'
            result['msg'] = '설정을 저장하지 못 했습니다.'
        return result

    def command_check_timeover(self, request: flask.Request) -> dict:
        num_range = self.parse_command(request)['query'].get('range', ['0~0'])[0]
        plexmate = PlexmateAider()
        plexmate.check_timeover(num_range)
        return self.returns('success', 'TIMEOUT 항목을 READY로 변경합니다.')

    def command_update_config_file(self, request: flask.Request) -> dict:
        aider = SettingAider()
        result = self.returns('warning', '업데이트를 실패했습니다.')
        try:
            response = aider.request('GET', 'https://raw.githubusercontent.com/halfaider/flaskfarmaider/main/files/flaskfarmaider.yaml')
            aider.config_from_file(response.text)
            result['ret'] = 'success'
            result['msg'] = '업데이트를 성공했습니다.'
        except:
            LOGGER.error(traceback.format_exc())
        return result

    def setting_save_after(self, changes: list) -> None:
        '''override'''
        super().setting_save_after(changes)
        for change in changes:
            match change:
                case 'setting_logging_login':
                    enable = CONFIG.get('setting_logging_login')
                    set_login_log(enable.lower() == 'true')

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()
        set_login_log(CONFIG.get('setting_logging_login').lower() == 'true')
        # 주기적 스캔 설정
        periodic_scan_enable = CONFIG.get_boolean('setting_plexmate_periodic_scan')
        if periodic_scan_enable:
            LOGGER.warning(f'새로고침 후 주기적 스캔 실행 기능은 곧 삭제됩니다. 주기적 스캔의 작업에서 직접 새로고침을 설정해 주세요.')


class Schedule(ModuleBase):

    _DB_VERSIONS = ['1', '2', '3', '4', '5', '6', '7']

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name='schedule')
        self.db_default = {
            'schedule_db_version': self._DB_VERSIONS[-1],
            'schedule_working_directory': '/',
            'schedule_last_list_option': ''
        }
        self.web_list_model = ScheduleModel

    def migration(self) -> None:
        '''override'''
        super().migration()
        self._migration('schedule_db_version', f'{PLUGIN.package_name}_schedules', migrate_schedule)

    def get_template_args(self) -> dict:
        '''override'''
        args = super().get_template_args()
        confs = [
            'schedule_working_directory',
            'schedule_last_list_option',
            'setting_rclone_remote_vfs',
            'setting_rclone_remote_vfses',
        ]
        for conf in confs:
            args[conf] = CONFIG.get(conf)
        try:
            plexmateaider = PlexmateAider()
            args['sections'] = plexmateaider.get_sections()
        except:
            LOGGER.error(traceback.format_exc())
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
        args['setting_rclone_remotes'] = CONFIG.get_json('setting_rclone_remotes')
        args['setting_rclone_mappings'] = CONFIG.get_json('setting_rclone_mappings')
        return args

    def add_schedule(self, id: int, schedule: ScheduleModel = None) -> bool:
        try:
            schedule = schedule or ScheduleModel.get_by_id(id)
            schedule_id = self.create_schedule_id(schedule.id)
            if not FRAMEWORK.scheduler.is_include(schedule_id):
                sch = FrameworkJob(__package__, schedule_id, schedule.schedule_interval, self.run_async, schedule.desc, args=(start_schedule, (schedule,)))
                FRAMEWORK.scheduler.add_job_instance(sch)
            return True
        except:
            LOGGER.error(traceback.format_exc())
            return False

    def set_schedule(self, id_: int | str, active: bool = False) -> tuple[bool, str]:
        schedule_id = self.create_schedule_id(id_)
        is_include = FRAMEWORK.scheduler.is_include(schedule_id)
        schedule = ScheduleModel.get_by_id(id_)
        schedule_mode = schedule.schedule_mode if schedule else FF_SCHEDULE_KEYS[0]
        match active, is_include:
            case True, True:
                result, msg = False, '이미 일정에 등록되어 있습니다.'
            case False, True:
                result, msg = FRAMEWORK.scheduler.remove_job(schedule_id), '일정에서 제외했습니다.'
            case False, False:
                result, msg = False, '등록되지 않은 일정입니다.'
            case True, False if schedule_mode == FF_SCHEDULE_KEYS[2]:
                result = self.add_schedule(id_)
                msg = '일정에 등록했습니다.' if result else '일정에 등록하지 못했어요.'
            case _:
                result, msg = False, '등록할 수 없는 일정 방식입니다.'
        return result, msg

    def reload_schedule(self, schedule: ScheduleModel, old_schedule: ScheduleModel) -> None:
        th = ThreadHasReturn(target=self._reload_schedule, args=(schedule, old_schedule), daemon=True, callback=self.callback_sio)
        th.start()

    def _reload_schedule(self, schedule: ScheduleModel, old_schedule: ScheduleModel) -> ScheduleModel:
        msg = ''
        schedule_id = self.create_schedule_id(schedule.id)
        if FRAMEWORK.scheduler.is_include(schedule_id) and \
            (old_schedule.schedule_mode != schedule.schedule_mode or \
            old_schedule.schedule_interval != schedule.schedule_interval):
            for _ in range(0, 60):
                FRAMEWORK.scheduler.remove_job(schedule_id)
                if not FRAMEWORK.scheduler.is_include(schedule_id):
                    break
                time.sleep(1)
            if schedule.schedule_mode == FF_SCHEDULE_KEYS[2]:
                if FRAMEWORK.scheduler.is_include(schedule_id):
                    msg = f'일정을 재등록 하지 못 했습니다: {schedule_id}'
                else:
                    self.add_schedule(schedule.id)
                    msg = f'일정을 재등록 했습니다: {schedule_id}'
                LOGGER.debug(msg)
        schedule = schedule.as_dict()
        schedule['is_include'] = FRAMEWORK.scheduler.is_include(schedule_id)
        schedule['msg'] = msg
        return schedule

    def create_schedule_id(self, id_: int, middle: str = 'schedule') -> str:
        return f'{PLUGIN.package_name}_{middle}_{id_}'

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()
        for schedule in ScheduleModel.get_list():
            if schedule.schedule_mode == FF_SCHEDULE_KEYS[1]:
                self.run_async(start_schedule, (schedule,))
            elif schedule.schedule_mode == FF_SCHEDULE_KEYS[2] and schedule.schedule_auto_start:
                self.add_schedule(schedule.id)
            if not schedule.status == STATUS_KEYS[0] and not schedule.schedule_mode == FF_SCHEDULE_KEYS[1]:
                LOGGER.warning(f'정상적으로 종료되지 않은 작업: {schedule.id} {schedule.desc}')
                schedule.set_status(STATUS_KEYS[0])

    def plugin_unload(self) -> None:
        '''override'''
        super().plugin_unload()
        for schedule in ScheduleModel.get_list():
            if not schedule.status == STATUS_KEYS[0]:
                LOGGER.warning(f'강제로 종료되는 작업: {schedule.id} {schedule.desc}')
                schedule.set_status(STATUS_KEYS[0])

    def update_schedule(self, id_: int, query: dict[str, list]) -> ScheduleModel:
        old_schedule = ScheduleModel.get(id_)
        schedule = ScheduleModel.update_formdata(id_, query)
        if old_schedule.id > 0:
            self.reload_schedule(schedule, old_schedule)
        return schedule

    def command_default(self, request: flask.Request) -> tuple[bool, str]:
        '''override'''
        parsed = self.parse_command(request)
        if parsed['command'] in TASK_KEYS:
            target = parsed['query'].get('target', [])
            if target:
                schedule = {
                    'task': parsed['command'],
                    'target': target[0],
                    'recursive': parsed['query'].get('recursive', ['false'])[0].lower() == 'true',
                    'scan_mode': parsed['query'].get('scan_mode', [SCAN_MODE_KEYS[0]])[0],
                    'rclone_remote': parsed['query'].get('rclone_remote', CONFIG.get_json('setting_rclone_remotes'))[0],
                }
                self.run_async(start_schedule, (ScheduleModel.get(info=schedule),))
                result, msg = True, '작업을 실행했습니다.'
            else:
                result, msg = False, '경로 정보가 없습니다.'
        else:
            result, msg = False, f'알 수 없는 명령입니다: {parsed["command"]}'
        return self.returns('success' if result else 'warning', msg)

    def command_list(self, request: flask.Request) -> dict:
        path = self.parse_command(request)['query'].get('target', ['/'])[0]
        try:
            dir_list = json.dumps(get_dir(path))
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            return self.returns('warning', str(e))
        CONFIG.set('schedule_working_directory', path)
        if dir_list:
            return self.returns('success', data=dir_list)
        else:
            return self.returns('warning', '폴더 목록을 생성할 수 없습니다.')

    def command_save(self, request: flask.Request) -> dict:
        parsed = self.parse_command(request)
        if len(parsed['ids']) > 1:
            if parsed['query']:
                for _id in parsed['ids']:
                    self.update_schedule(_id, parsed['query'].copy())
                return self.returns('success', '수정했습니다.')
            else:
                return self.returns('warning', '수정할 항목이 없습니다.')
        else:
            schedule = self.update_schedule(parsed['ids'][0], parsed['query'])
            if schedule.id > 0:
                return self.returns('success', '저장했습니다.')
            else:
                return self.returns('warning', '저장할 수 없습니다.')

    def command_delete(self, request: flask.Request) -> dict:
        parsed = self.parse_command(request)
        if len(parsed['ids']) > 1:
            not_deleted = []
            LOGGER.info(f'to be deleted: {parsed["ids"]}')
            for _id in parsed['ids']:
                if ScheduleModel.delete_by_id(_id):
                    self.set_schedule(_id, False)
                else:
                    not_deleted.append(_id)
            if len(not_deleted) > 0:
                LOGGER.warning(f'could not delete: {not_deleted}')
                return self.returns('warning', '일부는 삭제할 수 없었습니다.')
            else:
                return self.returns('success', '모두 삭제 했습니다.')
        else:
            if ScheduleModel.delete_by_id(parsed['ids'][0]):
                self.set_schedule(parsed['ids'][0], False)
                return self.returns('success', f'삭제 했습니다: ID {parsed["ids"][0]}')
            else:
                return self.returns('warning',  f'삭제할 수 없습니다: ID {parsed["ids"][0]}')

    def command_execute(self, request: flask.Request) -> dict:
        self.run_async(start_schedule, (ScheduleModel.get(self.parse_command(request)['ids'][0]),))
        return self.returns('success', '일정을 실행했습니다.')

    def command_schedule(self, request: flask.Request) -> dict:
        parsed = self.parse_command(request)
        active = parsed['query'].get('active', ['false'])[0].lower() == 'true'
        result, msg = self.set_schedule(parsed['ids'][0], active)
        return self.returns('success' if result else 'warning', msg)

    def command_get(self, request: flask.Request) -> dict:
        parsed = self.parse_command(request)
        schedule = ScheduleModel.get_by_id(parsed['ids'][0])
        if schedule:
            return self.returns('success', data=schedule.as_dict())
        else:
            return self.returns('warning', f'일정을 찾을 수 없습니다: ID {parsed["ids"][0]}')


class Manual(ModuleBase):

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


class Tool(ModuleBase):

    def __init__(self, plugin: PluginBase) -> None:
        super().__init__(plugin, name='tool', first_menu='trash')
        self.set_page_list([TrashTool, OAuthTool])

    def setting_save_after(self, changes: list) -> None:
        '''override'''
        super().setting_save_after(changes)
        for page in self.page_list:
            page.setting_save_after(changes)


class TrashTool(PageBase):

    def __init__(self, plugin: PluginBase, parent: ModuleBase) -> None:
        super().__init__(plugin, parent, name='trash')
        self.db_default = {
            'tool_trash_task_status': STATUS_KEYS[0],
            'tool_trash_last_list_option': ''
        }

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
        parsed = self.parse_command(request)
        section_type = parsed['query'].get('section_type', ['movie'])[0]
        section_id = int(parsed['query'].get('section_id', ['-1'])[0])
        page_no = int(parsed['query'].get('page', ['1'])[0])
        limit = int(parsed['query'].get('limit', ['30'])[0])
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
        parsed = self.parse_command(request)
        metadata_id = int(parsed['query'].get('metadata_id', ['-1'])[0])
        mediaitem_id = int(parsed['query'].get('mediaitem_id', ['-1'])[0])
        result, msg = PlexmateAider().delete_media(metadata_id, mediaitem_id)
        return self.returns('success' if result else 'warning', msg)

    @check_status
    def command_default(self, request: flask.Request) -> dict:
        '''override'''
        parsed = self.parse_command(request)
        if parsed['command'] in TOOL_TRASH_KEYS:
            schedule = ScheduleModel.get()
            schedule.task = parsed['command']
            schedule.section_id = int(parsed['query'].get('section_id', ['-1'])[0])
            schedule.rclone_remote = parsed['query'].get('rclone_remote', CONFIG.get_json('setting_rclone_remotes'))[0]
            schedule.recursive = False
            self.run_async(start_schedule, (schedule,))
            return self.returns('success', '작업을 실행했습니다.')
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
        for conf in self.db_default.keys():
            args[conf] = CONFIG.get(conf)
        args['setting_rclone_remotes'] = CONFIG.get_json('setting_rclone_remotes')
        return args

    def plugin_load(self) -> None:
        '''override'''
        super().plugin_load()
        CONFIG.set('tool_trash_task_status', STATUS_KEYS[0])

    def plugin_unload(self) -> None:
        '''override'''
        super().plugin_unload()
        CONFIG.set('tool_trash_task_status', STATUS_KEYS[0])


class OAuthTool(PageBase):

    def __init__(self, plugin: PluginBase, parent: ModuleBase) -> None:
        super().__init__(plugin, parent, name='oauth')
        self.db_default = {
            'tool_oauth_client_id': '',
            'tool_oauth_client_secret': '',
            'tool_oauth_refresh_token': '',
            'tool_oauth_scopes': '',
            'tool_oauth_redirect': '',
            'tool_oauth_credentials_json': '',
            'tool_oauth_rclone_token': '',
        }
        # https://github.com/oauthlib/oauthlib/blob/564d526fdbdc32a936e4b5ddac186c26024f626b/oauthlib/oauth2/rfc6749/parameters.py#L466
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'


    def get_template_args(self) -> dict:
        '''override'''
        args = super().get_template_args()
        for key in self.db_default:
            args[key] = CONFIG.get(key)
        return args

    def process_menu(self, req: flask.Request) -> flask.Response:
        '''override'''
        self.prerender(self.name, req)
        try:
            args = self.get_template_args()
            client_config = {
                'web': {
                    'client_id': CONFIG.get('tool_oauth_client_id'),
                    'client_secret': CONFIG.get('tool_oauth_client_secret'),
                    'redirect_uris': [CONFIG.get('tool_oauth_redirect')],
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://accounts.google.com/o/oauth2/token',
                    'auth_provider_x509_cert_url': 'https://www.googleapis.com/oauth2/v1/certs'
                }
            }
            if req.args.get('command') == 'authorize':
                flow = google_auth_oauthlib.flow.Flow.from_client_config(client_config, CONFIG.get_list('tool_oauth_scopes'), redirect_uri=CONFIG.get('tool_oauth_redirect'))
                authorization_url, state = flow.authorization_url(access_type='offline', prompt='consent', include_granted_scopes='true')
                flask.session['oauth_state'] = state
                return flask.redirect(authorization_url)
            if req.args.get('code') and req.args.get('state'):
                state = flask.session['oauth_state']
                flow = google_auth_oauthlib.flow.Flow.from_client_config(client_config, CONFIG.get_list('tool_oauth_scopes'), redirect_uri=CONFIG.get('tool_oauth_redirect'), state=state)
                flow.fetch_token(code=req.args.get('code'))
                expiry = flow.credentials.expiry.replace(tzinfo=datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')
                rclone_token = {
                    'access_token': flow.credentials.token,
                    'token_type': 'Bearer',
                    'refresh_token': flow.credentials.refresh_token,
                    'expiry': f'{expiry}+00:00',
                }
                CONFIG.set('tool_oauth_refresh_token', flow.credentials.refresh_token)
                CONFIG.set('tool_oauth_credentials_json', flow.credentials.to_json())
                CONFIG.set('tool_oauth_rclone_token', json.dumps(rclone_token, separators=(',', ':')))
                return flask.redirect(CONFIG.get('tool_oauth_redirect'))
            return flask.render_template(f'{PLUGIN.package_name}_{self.parent.name}_{self.name}.html', args=args)
        except:
            self.P.logger.error(traceback.format_exc())
            return flask.render_template('sample.html', title=f"process_menu() - {PLUGIN.package_name}/{self.parent.name}/{self.name}")

    def command_save(self, request: flask.Request) -> dict:
        parsed = self.parse_command(request)
        LOGGER.info(parsed)
        for key in parsed['query']:
            CONFIG.set(key, parsed['query'][key][0])
        return self.returns('success', '저장했습니다.')


@FRAMEWORK.celery.task(bind=True)
def start_schedule(task, schedule: ScheduleModel) -> dict:
    try:
        if schedule.id and schedule.id > 0:
            schedule.set_status(STATUS_KEYS[1])
        if schedule.task in TOOL_TRASH_KEYS:
            CONFIG.set('tool_trash_task_status', STATUS_KEYS[1])
        aider = ScheduleAider()
        getattr(aider, f'start_{schedule.task}')(schedule)
        msg = '작업이 끝났습니다.'
    except Exception as e:
        LOGGER.error(traceback.format_exc())
        msg = str(e)
    finally:
        if schedule.id and schedule.id > 0:
            schedule.set_status(STATUS_KEYS[2])
        if schedule.task in TOOL_TRASH_KEYS:
            CONFIG.set('tool_trash_task_status', STATUS_KEYS[0])
        schedule = schedule.as_dict()
        schedule['msg'] = msg
        return schedule
