import pathlib
import datetime
import traceback
import shutil
import sqlite3
import subprocess
import shlex
import locale
import platform
import time
import urllib.parse
import functools
from typing import Any, Callable

import yaml

from .setup import FRAMEWORK, LOGGER, CONFIG
from .api import Aider, PluginAider
from .models import ScheduleModel
from .constants import TASK_KEYS, TOOL_TRASH_KEYS, STATUS_KEYS, SCAN_MODE_KEYS, SECTION_TYPE_KEYS
from .util import dict_factory, get_readable_time, parse_mappings, update_path, parse_json_response


class ScheduleAider(Aider):

    def start_trash(self, schedule: ScheduleModel) -> None:
        refresh = scan = empty = False
        if schedule.task in (TOOL_TRASH_KEYS[0], TOOL_TRASH_KEYS[3], TOOL_TRASH_KEYS[4]):
            refresh = True
        if schedule.task in (TOOL_TRASH_KEYS[1], TOOL_TRASH_KEYS[3], TOOL_TRASH_KEYS[4]):
            scan = True
        if schedule.task in (TOOL_TRASH_KEYS[2], TOOL_TRASH_KEYS[4]):
            empty = True
        plex_aider = PlexmateAider()
        if not schedule.task == TOOL_TRASH_KEYS[2]:
            rclone_aider = RcloneAider(schedule.rclone_remote)
            trashes: dict = plex_aider.get_trashes(schedule.section_id, 1, -1)
            if trashes:
                paths: set[str] = {pathlib.Path(row['file']).parent.as_posix() for row in trashes}
                for path in paths:
                    if CONFIG.get('tool_trash_task_status') != STATUS_KEYS[1]:
                        LOGGER.info('작업을 중지합니다.')
                        break
                    if refresh:
                        rclone_aider.vfs_refresh(path, schedule.recursive)
                    if scan:
                        plex_aider.scan(SCAN_MODE_KEYS[0], path, schedule.section_id)
            else:
                LOGGER.info('이용 불가 파일이 없습니다.')
                empty = False
        if empty and CONFIG.get('tool_trash_task_status') == STATUS_KEYS[1]:
            plex_aider.empty_trash(schedule.section_id)

    def start_trash_refresh(self, schedule: ScheduleModel) -> None:
        self.start_trash(schedule)

    def start_trash_scan(self, schedule: ScheduleModel) -> None:
        self.start_trash(schedule)

    def start_trash_empty(self, schedule: ScheduleModel) -> None:
        self.start_trash(schedule)

    def start_trash_refresh_scan(self, schedule: ScheduleModel) -> None:
        self.start_trash(schedule)

    def start_trash_refresh_scan_empty(self, schedule: ScheduleModel) -> None:
        self.start_trash(schedule)

    def start_forget(self, schedule: ScheduleModel) -> None:
        '''forget'''
        RcloneAider(schedule.rclone_remote).vfs_forget(schedule.target)

    def start_startup(self, schedule: ScheduleModel) -> None:
        '''startup'''
        platform_name = platform.system().lower()
        LOGGER.debug(f'플랫폼: {platform_name}')
        if platform_name == 'windows':
            WindowsAider().startup()
        elif platform_name == 'linux':
            UbuntuAider().startup()
        else:
            LOGGER.warning(f'실행할 수 없는 OS 환경입니다: {platform_name}')

    def start_clear(self, schedule: ScheduleModel) -> None:
        '''clear'''
        PlexmateAider().clear_section(schedule.clear_section, schedule.clear_type, schedule.clear_level)

    def start_pm_ready_refresh(self, schedule: ScheduleModel) -> None:
        '''pm_ready_refresh'''
        plex_aider = PlexmateAider()
        rclone_aider = RcloneAider(schedule.rclone_remote)
        # plexmate
        plex_aider.check_scanning(CONFIG.get_int('setting_plexmate_max_scan_time') or 0)
        plex_aider.check_timeover(CONFIG.get('setting_plexmate_timeover_range') or '0~0')
        # refresh
        targets = {s for s in plex_aider.get_scan_items('READY')}
        if targets:
            for target in targets:
                if target.mode in ('REMOVE_FILE', 'REMOVE_FOLDER'):
                    rclone_aider.vfs_forget(target.target)
                else:
                    rclone_aider.vfs_refresh(target.target, schedule.recursive)
        else:
            LOGGER.info('plex_mate: 새로고침 대상이 없습니다.')

    def start_scan(self, schedule: ScheduleModel) -> None:
        '''scan'''
        plex_aider = PlexmateAider()
        # 스캔 작업 포함시 get_scan_targets()으로 대상 한정
        targets = plex_aider.get_scan_targets(schedule.target, schedule.section_id)
        for location, section_id in targets.items():
            plex_aider.scan(schedule.scan_mode, location, section_id=section_id)

    def start_refresh(self, schedule: ScheduleModel) -> None:
        '''refresh'''
        rclone_aider = RcloneAider(schedule.rclone_remote)
        if schedule.section_id and int(schedule.section_id) > 0:
            targets = PlexmateAider().get_scan_targets(schedule.target, schedule.section_id)
            for location, _ in targets.items():
                rclone_aider.vfs_refresh(location, schedule.recursive)
        else:
            rclone_aider.vfs_refresh(schedule.target, schedule.recursive)

    def start_refresh_scan(self, schedule: ScheduleModel) -> None:
        '''refresh_scan'''
        plex_aider = PlexmateAider()
        rclone_aider = RcloneAider(schedule.rclone_remote)
        # 스캔 작업 포함시 get_scan_targets()으로 대상 한정
        targets = plex_aider.get_scan_targets(schedule.target, schedule.section_id)
        for location, section_id in targets.items():
            rclone_aider.vfs_refresh(location, schedule.recursive)
            plex_aider.scan(schedule.scan_mode, location, section_id=section_id)


class SettingAider(Aider):

    @staticmethod
    def config_from_file(text: str = None) -> str | None:
        try:
            source_config = pathlib.Path(__file__).parent / 'files' / f'{__package__}.yaml'
            user_config = pathlib.Path(CONFIG.get('setting_config_file'))
            if not user_config.exists():
                shutil.copyfile(source_config, user_config)
            with user_config.open(mode='r+', encoding='utf-8', newline='\n') as file:
                if text is None:
                    depends = file.read()
                else:
                    file.truncate(0)
                    file.write(text)
                    depends = text
            return depends
        except:
            LOGGER.error(traceback.format_exc())


class PlexmateAider(PluginAider):

    def __init__(self) -> None:
        super().__init__('plex_mate')
        self.db = self.plugin.PlexDBHandle

    def get_scan_model(self) -> ScheduleModel:
        return self.get_module('scan').web_list_model

    def get_scan_items(self, status: str) -> list[ScheduleModel]:
        return self.get_scan_model().get_list_by_status(status)

    def get_sections(self) -> dict:
        return {
            SECTION_TYPE_KEYS[0]: [{'id': item['id'], 'name': item['name']} for item in self.db.library_sections(section_type=1)],
            SECTION_TYPE_KEYS[1]: [{'id': item['id'], 'name': item['name']} for item in self.db.library_sections(section_type=2)],
            SECTION_TYPE_KEYS[2]: [{'id': item['id'], 'name': item['name']} for item in self.db.library_sections(section_type=8)],
            SECTION_TYPE_KEYS[3]: [{'id': item['id'], 'name': item['name']} for item in self.db.library_sections(section_type=13)],
        }

    def get_periodics(self) -> list[dict]:
        periodics = []
        jobs = self.get_module('periodic').get_jobs()
        for job in jobs:
            idx = int(job['job_id'].replace('plex_mate_periodic_', '')) + 1
            section = job.get('섹션ID', -1)
            section_data = self.db.library_section(section)
            if section_data:
                name = section_data.get('name')
            else:
                LOGGER.debug(f'존재하지 않는 섹션: {section}')
                continue
            periodics.append({'idx': idx, 'name': name, 'desc': job.get('설명', '')})
        return periodics

    def get_trashes(self, section_id: int, page_no: int = 1, limit: int = 10) -> list[dict]:
        query = '''
        SELECT media_items.id, media_items.metadata_item_id, media_items.deleted_at, media_parts.file, media_parts.deleted_at
        FROM media_parts, media_items
        WHERE media_parts.deleted_at != ''
            AND media_items.library_section_id = {section_id}
            AND media_items.id = media_parts.media_item_id
        ORDER BY media_parts.file
        LIMIT {limit} OFFSET {offset}
        '''
        offset = (page_no - 1) * limit
        with sqlite3.connect(self.plugin.ModelSetting.get('base_path_db')) as con:
            con.row_factory = dict_factory
            cs = con.cursor()
            return cs.execute(query.format(section_id=section_id, limit=limit, offset=offset)).fetchall()

    def get_trash_list(self, section_id: int, page_no: int = 1, limit: int = 10) -> dict:
        result = {'total': 0, 'limit': limit, 'page': page_no, 'section_id': section_id, 'total_paths': 0, 'data': None}
        total_rows = self.get_trashes(section_id, 1, -1)
        paths ={pathlib.Path(row['file']).parent.as_posix() for row in total_rows}
        result['total'] = len(total_rows)
        result['total_paths'] = len(paths)
        rows = self.get_trashes(section_id, page_no, limit)
        if len(rows) > 0:
            for row in rows:
                row['deleted_at'] = get_readable_time(row['deleted_at'])
            result['data'] = rows
        return result

    def check_scanning(self, max_scan_time: int) -> None:
        '''
        SCANNING 항목 점검.

        배경:
            PLEX_MATE에서 특정 폴더가 비정상적으로 계속 SCANNING 상태이면 이후 동일 폴더에 대한 스캔 요청이 모두 무시됨.
            예를 들어 .plexignore 가 있는 폴더는 PLEX_MATE 입장에서 스캔이 정상 종료되지 않기 때문에 계속 SCANNING 상태로 유지됨.
            이 상태에서 동일한 폴더에 새로운 미디어가 추가되면 스캔이 되지 않고 FINISH_ALREADY_IN_QUEUE 로 종료됨.
        검토:
            flaskfarm은 파이썬으로 실행되는 프로세스와 셀러리로 실행되는 프로세스 2개로 작동 함.
            그래서 셀러리에서 로딩한 Framework 인스턴스와 파이썬으로 로딩한 Framework 인스턴스가 다름.
            plex_mate.task_scan.Task.filecheck_thread_function() 은 start_celery() 로 인해 셀러리 apply_async() 로 실행됨.
            즉, 파일 체크 스레드는 셀러리 프로세스로 실행됨.
            파일 체크 스레드가 참조하는 ModelScanItem.queue_list에 접근하려면 셀러리로 실행 되어야 함.
        대안:
            1. plex_mate와 동일하게 셀러리 task 로 작업을 실행
            2. DB를 직접 조작하여 SCANNING 아이템 제거
                - 스캔 오류라고 판단된 item을 db에서 삭제하고 동일한 id로 새로운 item을 db에 생성
                - ModelScanItem.queue_list에는 기존 item의 객체가 아직 남아 있음.
                - 다음 파일체크 단계에서 queue_list에 남아있는 기존 item 정보로 인해 새로운 item의 STATUS가 FINISH_ALREADY_IN_QUEUE로 변경됨.
                - FINISH_* 상태가 되면 ModelScanItem.remove_in_queue()가 호출됨.
                - 새로운 item 객체는 기존 item 객체의 id를 가지고 있기 때문에 queue_list에서 기존 item 객체가 제외됨.
        주의:
            계속 SCANNING 상태로 유지되는 항목은 확인 후 조치.
        '''
        scans = self.get_scan_items('SCANNING') or ()
        model = self.get_scan_model()
        for scan in scans:
            if int((datetime.datetime.now() - scan.process_start_time).total_seconds() / 60) >= max_scan_time:
                LOGGER.warning(f'스캔 시간 {max_scan_time}분 초과: {scan.target}')
                LOGGER.warning(f'스캔 QUEUE에서 제외: {scan.target}')
                # 대안 1
                scan.remove_in_queue(scan)
                scan.set_status('FINISH_TIMEOVER', save=True)
                '''
                # 대안 2
                model.delete_by_id(scan.id)
                new_item = model(scan.target)
                new_item.id = scan.id
                new_item.save()
                '''

    def check_timeover(self, item_range: str) -> None:
        '''
        FINISH_TIMEOVER 항목 점검
        ID가 item_range 범위 안에 있는 TIMEOVER 항목들을 다시 READY 로 변경
        주의: 계속 시간 초과로 뜨는 항목은 확인 후 수동으로 조치
        '''
        overs = self.get_scan_items('FINISH_TIMEOVER') or ()
        start_id, end_id = list(map(int, item_range.split('~')))
        for over in overs:
            if over.id in range(start_id, end_id + 1):
                LOGGER.warning(f'READY 로 상태 변경: {over.id} {over.target}')
                over.filecheck_count = 0
                over.created_time = datetime.datetime.now()
                over.set_status('READY', save=True)

    def get_scan_targets(self, target: str, section_id: int = None) -> dict[str, int]:
        mappings = parse_mappings(CONFIG.get_json('setting_plex_mappings'))
        target = pathlib.Path(update_path(target, mappings))
        if section_id and int(section_id) > 0:
            locations = self.db.select(f'SELECT library_section_id, root_path FROM section_locations WHERE library_section_id = {section_id}')
        else:
            locations = self.db.select('SELECT library_section_id, root_path FROM section_locations')
        targets = {}
        for location in locations:
            root = pathlib.Path(f'{location["root_path"]}')
            root = pathlib.Path(root.as_posix())
            if target.is_relative_to(root):
                targets[target.as_posix()] = int(location['library_section_id'])
            elif root.is_relative_to(target):
                targets[root.as_posix()] = int(location['library_section_id'])
        if targets:
            LOGGER.debug(f'섹션 ID 검색 결과: {set(targets.values())}')
        else:
            LOGGER.error(f'섹션 ID를 찾을 수 없습니다: {target}')
        return targets

    def web_scan(self, section_id: int, location: str = None) -> None:
        url = f'{self.plugin.ModelSetting.get("base_url")}/library/sections/{section_id}/refresh'
        params = {
            'X-Plex-Token': self.plugin.ModelSetting.get('base_token'),
            'path': location,
        }
        section = self.get_section_by_id(section_id)

        response = self.request('GET', url, params=params)
        if str(response.status_code)[0] == '2':
            LOGGER.info(f'스캔 전송: {section.get("name")}: {location}')
        else:
            LOGGER.error(f'스캔 전송 실패: {response.text}')

    def scan(self, scan_mode: str, target: str = None, section_id: int = -1) -> None:
        if scan_mode == SCAN_MODE_KEYS[0]:
            '''
            웹 스캔의 완료를 추적하는 방식이 정확하지 않음.
                - 스캔이 밀려 있을 경우 activity는 현재 스캔만 보여줌
                - library_sections 테이블의 updated_at이 스캔 종료 후 1분 뒤에 변경됨
            서버에 스캔 명령만 전달하는 방식으로 실행(서버에서 알아서 순차적으로 스캔하도록...)
            '''
            self.web_scan(section_id, target)
            #before = self.get_section_updated_at(section_id)
            #for i in range(120):
            #    after = self.get_section_updated_at(section_id)
            #    LOGGER.info(f"{before=}")
            #    LOGGER.info(f"{after=}")
            #    time.sleep(1)
        else:
            scan_item = self.get_scan_model()(target)
            scan_item.save()
            LOGGER.info(f'plex_mate 스캔 ID: {scan_item.id}')

    def get_locations_by_id(self, section_id: int) -> list[str]:
        return [location.get('root_path') for location in self.db.section_location(library_id=section_id)]

    def get_section_by_id(self, section_id: int) -> dict:
        return self.db.library_section(section_id)

    def get_periodic_locations(self, periodic_id: int) -> list[str]:
        job = self.get_periodic_job(periodic_id)
        try:
            if job.get('폴더'):
                targets = list(job.get('폴더'))
            else:
                targets = self.get_locations_by_id(job.get('섹션ID'))
        except:
            LOGGER.error(traceback.format_exc())
            targets = []
        finally:
            return targets

    def get_periodic_job(self, periodic_id: int) -> dict:
        mod = self.get_module('periodic')
        periodic_id -= 1
        try:
            job = mod.get_jobs()[periodic_id]
        except IndexError:
            LOGGER.error(f'주기적 스캔 작업을 찾을 수 없습니다: {periodic_id + 1}')
            job = {}
        finally:
            return job

    def get_section_updated_at(self, section_id: int) -> int:
        return self.db.library_section(section_id)['updated_at']

    def clear_section(self, section_id: int, clear_type: str, clear_level: str) -> None:
        mod = self.get_module('clear')
        page = mod.get_page(clear_type)
        sec = self.get_section_by_id(section_id)
        if sec:
            info = f'{clear_level}, {sec.get("name")}'
            LOGGER.info(f'파일 정리 시작: {info}')
            page.task_interface(clear_level, section_id, 'false').join()
            LOGGER.info(f'파일 정리 종료: {info}')
        else:
            LOGGER.warning(f'존재하지 않는 섹션입니다: {section_id}')

    def delete_media(self, meta_id: int, media_id: int) -> tuple[bool, str]:
        url = f'{self.plugin.ModelSetting.get("base_url")}/library/metadata/{meta_id}/media/{media_id}'
        params = {
            'X-Plex-Token': self.plugin.ModelSetting.get('base_token')
        }
        try:
            response = self.request('DELETE', url, params=params)
            if str(response.status_code)[0] == '2':
                return True, f'삭제했습니다: {media_id}'
            else:
                raise Exception(f'삭제할 수 없습니다: {response.text}')
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            return False, str(e)

    def empty_trash(self, section_id: int) -> None:
        url = f'{self.plugin.ModelSetting.get("base_url")}/library/sections/{section_id}/emptyTrash'
        params = {
            'X-Plex-Token': self.plugin.ModelSetting.get('base_token')
        }
        section = self.get_section_by_id(section_id)

        counter = 0
        while self.check_library_update(section_id):
            time.sleep(10)
            counter += 1
            if counter > 36:
                LOGGER.error(f'라이브러리({section_id})를 스캔 중이라 휴지통 비우기를 취소합니다.')
                return
        response = self.request('PUT', url, params=params)
        if str(response.status_code)[0] == '2':
            LOGGER.info(f'휴지통 비우기 명령을 전송했습니다: {section.get("name")}')
        else:
            LOGGER.error(f'휴지통 비우기 명령을 전달할 수 없습니다: {response.text}')

    def get_activities(self) -> dict:
        url = f'{self.plugin.ModelSetting.get("base_url")}/activities'
        params = {
            'X-Plex-Token': self.plugin.ModelSetting.get('base_token')
        }
        headers = {
            'Accept': 'application/json',
        }
        try:
            response = self.request('GET', url, params=params, headers=headers)
            return response.json()
        except:
            LOGGER.error(traceback.format_exc())
            return {}

    def check_library_update(self, section_id: int) -> bool:
        container = self.get_activities().get('MediaContainer')
        if container:
            for act in container.get('Activity', []):
                if act.get('type') == 'library.update.section':
                    updating_section_id = int(act.get('Context', {}).get('librarySectionID'))
                    if updating_section_id == section_id:
                        LOGGER.debug(f"status=scanning section_id={updating_section_id} title='{act.get('title')}' progress={act.get('progress')}")
                        return True
        return False


class RcloneAider(Aider):

    def __init__(self, rc_url: str = None) -> None:
        super().__init__()
        url = urllib.parse.urlparse(rc_url)
        if not url.netloc or not url.scheme:
            raise Exception(f'Rclone RC 리모트 주소를 입력하세요: {rc_url}')
        self._vfs = url.fragment
        self._rc_user = url.username
        self._rc_pass = url.password
        try:
            self._rc_url = urllib.parse.urlunparse([url.scheme, url.netloc, '', '', '', ''])
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            LOGGER.error(f'url: {url}')
            raise e
        self._mappings = parse_mappings(CONFIG.get_json('setting_rclone_mappings'))

    @property
    def rc_url(self) -> str:
        return self._rc_url

    @property
    def rc_user(self) -> str:
        return self._rc_user

    @property
    def rc_pass(self) -> str:
        return self._rc_pass

    @property
    def vfs(self) -> str:
        return self._vfs

    @property
    def mappings(self) -> str:
        return self._mappings

    def command(method: Callable) -> Callable:
        @functools.wraps(method)
        def wrapper(self, *args: tuple, **kwds: dict) -> dict[str, Any]:
            data = method(self, *args, **kwds)
            vfs = data.pop('fs', None)
            if vfs:
                data['fs'] = f'{vfs}:'
            dir = data.get('dir')
            if not dir or dir == '/':
                data.pop('dir', None)
            command = '/'.join(method.__name__.split('__'))
            interface = data.pop('interface', 'API')
            # CLI or API
            if interface == 'CLI':
                command_method = self.command_cli
            else:
                command_method = self.command_api
            result = command_method(command, data)
            if result.get('error'):
                LOGGER.error(result)
                raise Exception(result.get('error'))
            return result
        return wrapper

    def check_metadata_cache(method: Callable) -> Callable:
        @functools.wraps(method)
        def wrapper(self, *args: tuple, **kwds: dict) -> dict[str, Any]:
            start_dirs, start_files = self.get_metadata_cache()
            start = time.time()
            result = method(self, *args, **kwds)
            elapsed = time.time() - start
            dirs, files = self.get_metadata_cache()
            LOGGER.info(f'dirs={dirs - start_dirs} files={files - start_files} elapsed={elapsed:.1f}s result="{result!r}"')
            return result
        return wrapper

    def command_api(self, command: str, data: dict = None) -> dict[str, Any]:
        LOGGER.debug(f'{command}: {data}')
        return parse_json_response(self.request('JSON', f'{self.rc_url}/{command}', data=data, auth=(self.rc_user, self.rc_pass)))

    def command_cli(self, command: str, data: dict = None):
        pass

    @command
    def vfs__list(self, interface: str = None) -> dict[str, Any]:
        return {'interface': interface}

    @command
    def vfs__stats(self, fs: str = None, interface: str = None) -> dict[str, Any]:
        return {
            'interface': interface,
            'fs': fs or self.vfs,
        }

    @command
    def vfs__refresh(self, remote_path: str = None, recursive: bool = False, fs: str = None, interface: str = None) -> dict[str, Any]:
        data = {
            'recursive': f'{bool(recursive)}'.lower(),
            'interface': interface,
            'fs': fs or self.vfs,
        }
        if remote_path:
            data['dir'] = remote_path
        return data

    @command
    def vfs__forget(self, remote_path: str, fs: str = None, interface: str = None) -> dict[str, Any]:
        return {
            'interface': interface,
            'dir': remote_path,
            'fs': fs or self.vfs,
        }

    @command
    def job__list(self, interface: str = None) -> dict[str, Any]:
        return {'interface': interface}

    @command
    def job__status(self, jobid: int, interface: str = None) -> dict[str, Any]:
        return {
            'interface': interface,
            'jobid': jobid,
        }

    @command
    def job__stop(self, jobid: int, interface: str = None) -> dict[str, Any]:
        return {
            'interface': interface,
            'jobid': jobid,
        }

    @command
    def job__stopgroup(self, group: str, interface: str = None) -> dict[str, Any]:
        return {
            'interface': interface,
            'group': group,
        }

    @command
    def core__stats(self, interface: str = None) -> dict[str, Any]:
        return {'interface': interface}

    @check_metadata_cache
    def _vfs_refresh(self, remote_path: str = None, recursive: bool = False, fs: str = None) -> dict[str, Any]:
        result: dict = self.vfs__refresh(remote_path, recursive, fs)
        return result

    def vfs_refresh(self, local_path: str, recursive: bool = False, fs: str = None) -> None:
        remote_path = pathlib.Path(update_path(str(local_path), self.mappings)) if self.mappings else local_path
        for parent in remote_path.parents:
            if parent == parent.parent:
                result = self._vfs_refresh() or {}
            else:
                result = self._vfs_refresh(parent.as_posix()) or {}
            LOGGER.info(f'Rclone: {result}')
            if ((result.get('result') or {}).get(parent.as_posix()) or '').lower() == 'ok':
                break
            if (result.get('result') or {}).get('error'):
                return
        else:
            LOGGER.warning(f'It has hit the root path: "{remote_path.as_posix()}"')
        if not pathlib.Path(local_path).is_file():
            result = self._vfs_refresh(remote_path.as_posix(), recursive)
            LOGGER.info(f'Rclone: {result}')

    @check_metadata_cache
    def _vfs_forget(self, remote_path: str, fs: str = None) -> dict[str, Any]:
        result: dict = self.vfs__forget(remote_path, fs)
        return result

    def vfs_forget(self, local_path: str, fs: str = None) -> None:
        remote_path = pathlib.Path(update_path(local_path, self.mappings)) if self.mappings else pathlib.Path(local_path)
        self._vfs_forget(remote_path.as_posix(), fs)

    def get_metadata_cache(self, fs: str = None) -> tuple[int, int]:
        try:
            result = self.vfs__stats(fs)
            result = result.get('metadataCache')
            return result.get('dirs', 0), result.get('files', 0)
        except Exception as e:
            LOGGER.warning(repr(e))
            return 0, 0


class StartupAider(Aider):

    def __init__(self) -> None:
        super().__init__()

    def sub_run(self, *args: tuple[str],
                stdout: int = subprocess.PIPE, stderr: int = subprocess.STDOUT,
                encoding: str = locale.getpreferredencoding(),
                **kwds: dict) -> subprocess.CompletedProcess:
        startup_executable = CONFIG.get('setting_startup_executable')
        startup_executable = startup_executable.lower() == 'true'
        if not startup_executable:
            msg = '실행이 허용되지 않았어요.'
            LOGGER.error(msg)
            return subprocess.CompletedProcess(args, returncode=1, stderr='', stdout=msg)
        else:
            try:
                # shell=True는 의도치 않은 명령이 실행될 수 있으니 항상 False로...
                if kwds.get('shell'):
                    kwds['shell'] = False
                return subprocess.run(args, stdout=stdout, stderr=stderr, encoding=encoding, **kwds)
            except Exception as e:
                LOGGER.error(traceback.format_exc())
                return subprocess.CompletedProcess(args, returncode=1, stderr='', stdout=str(e))

    def startup(self) -> None:
        plugins_installed = self.get_installed_plugins()
        content = SettingAider.config_from_file()
        if content:
            depends = yaml.safe_load(content).get('dependencies')
        else:
            depends = {}

        require_plugins, require_packages, require_commands = self.get_require_plugins(plugins_installed, depends)

        # 1. Commands from the setting
        executable_commands = CONFIG.get_json('setting_startup_commands')
        # 2. Commands of installing required packages
        executable_commands.extend(self.get_commands_from_packages(require_packages))
        # 3. Commands from plugin dependencies
        executable_commands.extend(require_commands)

        if require_plugins:
            for plugin in require_plugins:
                LOGGER.info(f'설치 예정 플러그인: {plugin}')

        for command in executable_commands:
            LOGGER.info(f'실행 예정 명령어: {command}')

        self.execute(executable_commands, require_plugins, depends)

    def execute(self, commands: list[str], require_plugins: set[str] = {}, depends: dict = {}) -> None:
        startup_executable = CONFIG.get('setting_startup_executable')
        startup_executable = startup_executable.lower() == 'true'
        if startup_executable:
            for command in commands:
                if not command:
                    continue
                command = shlex.split(command)
                timeout = CONFIG.get_int('setting_startup_timeout') or 0
                timeout = timeout if timeout > 0 else None
                result: subprocess.CompletedProcess = self.sub_run(*command, timeout=timeout)
                if result.returncode == 0:
                    msg = '성공'
                else:
                    msg = result.stdout
                LOGGER.info(f'실행 결과 {command}: {msg}')

            for plugin in require_plugins:
                result = FRAMEWORK.PluginManager.plugin_install(depends.get(plugin, {"repo": "NO INFO."}).get("repo"))
                LOGGER.info(result.get('msg'))
        else:
            LOGGER.warning('실행이 허용되지 않았어요.')

    def get_installed_plugins(self) -> dict:
        return FRAMEWORK.PluginManager.all_package_list

    def get_require_plugins(self, plugins_installed: dict, depends) -> tuple[set, set, set]:
        require_plugins = set()
        require_packages = set()
        require_commands = set()
        # plugin by plugin
        for plugin in plugins_installed.keys():
            # append this plugin's requires to
            depend_plugins = depends.get(plugin, {}).get('plugins', [])
            for depend in depend_plugins:
                if depend not in plugins_installed:
                    require_plugins.add(depend)

            # append this plugin's packages to
            for depend in depends.get(plugin, {}).get('packages', []):
                require_packages.add(depend)

            # append this plugin's commands to
            for depend in depends.get(plugin, {}).get('commands', []):
                require_commands.add(depend)
        return require_plugins, require_packages, require_commands

    def get_commands_from_packages(self, require_packages) -> list[str]:
        pass


class UbuntuAider(StartupAider):

    def __init__(self) -> None:
        super().__init__()

    def get_commands_from_packages(self, require_packages) -> list[str]:
        return [f'apt-get install -y {req}' for req in require_packages]


class WindowsAider(StartupAider):

    def __init__(self) -> None:
        super().__init__()

    def get_commands_from_packages(self, require_packages) -> list[str]:
        LOGGER.warning('윈도우는 패키지 설치 명령어를 "commands" 혹은 "실행할 명령어"로 실행')
        return []
