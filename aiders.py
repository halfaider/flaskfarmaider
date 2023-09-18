import os
from pathlib import Path
from datetime import datetime
from typing import Any
import traceback
import shutil
import yaml
import sqlite3
import functools
import subprocess
from subprocess import CompletedProcess
import shlex
import platform
import time
import locale

import requests
from requests import Response

from .setup import PluginModuleBase, ModelBase
from .setup import FRAMEWORK, LOGGER,  DEPEND_USER_YAML, CONFIG
from .constants import *


class Aider:

    def __init__(self, name: str = None) -> None:
        self.name = name

    def get_readable_time(self, _time: float) -> str:
        return datetime.utcfromtimestamp(_time).strftime('%b %d %H:%M')

    def parse_mappings(self, text: str) -> dict[str, str]:
        mappings = {}
        if text:
            settings = text.splitlines()
            for setting in settings:
                source, target = setting.split(':')
                mappings[source.strip()] = target.strip()
        return mappings

    def update_path(self, target: str, mappings: dict) -> str:
        for k, v in mappings.items():
            target = target.replace(k, v)
        return target

    def request(self, method: str = 'POST', url: str = None, data: dict = None, **kwds: Any) -> Response:
        try:
            if method.upper() == 'JSON':
                return requests.request('POST', url, json=data or {}, **kwds)
            else:
                return requests.request(method, url, data=data, **kwds)
        except:
            tb = traceback.format_exc()
            LOGGER.error(tb)
            response = requests.Response()
            response._content = bytes(tb, 'utf-8')
            response.status_code = 0
            return response


class JobAider(Aider):

    def __init__(self) -> None:
        super().__init__()
        self.starts = {
            TASK_KEYS[0]: self.start_refresh_scan,
            TASK_KEYS[1]: self.start_refresh,
            TASK_KEYS[2]: self.start_scan,
            TASK_KEYS[3]: self.start_pm_ready_refresh,
            TASK_KEYS[4]: self.start_clear,
            TASK_KEYS[5]: self.start_startup,
            TASK_KEYS[6]: self.start_forget,
            TOOL_TRASH_KEYS[0]: self.start_trash,
            TOOL_TRASH_KEYS[1]: self.start_trash,
            TOOL_TRASH_KEYS[2]: self.start_trash,
            TOOL_TRASH_KEYS[3]: self.start_trash,
            TOOL_TRASH_KEYS[4]: self.start_trash,
        }

    def start_trash(self, job: ModelBase) -> None:
        refresh = scan = empty = False
        if job.task in [TOOL_TRASH_KEYS[0], TOOL_TRASH_KEYS[3], TOOL_TRASH_KEYS[4]]:
            refresh = True
        if job.task in [TOOL_TRASH_KEYS[1], TOOL_TRASH_KEYS[3], TOOL_TRASH_KEYS[4]]:
            scan = True
        if job.task in [TOOL_TRASH_KEYS[2], TOOL_TRASH_KEYS[4]]:
            empty = True
        plex_aider = PlexmateAider()
        if not job.task == TOOL_TRASH_KEYS[2]:
            rclone_aider = RcloneAider()
            trashes: dict = plex_aider.get_trashes(job.section_id, 1, -1)
            paths = {Path(row['file']).parent for row in trashes}
            for path in paths:
                if CONFIG.get(TOOL_TRASH_TASK_STATUS) != STATUS_KEYS[1]:
                    LOGGER.info(f'작업을 중지합니다.')
                    break
                if refresh:
                    rclone_aider.vfs_refresh(path, job.recursive, job.vfs)
                if scan:
                    plex_aider.scan(SCAN_MODE_KEYS[2], str(path), -1, job.section_id)
        if empty and CONFIG.get(TOOL_TRASH_TASK_STATUS) == STATUS_KEYS[1]:
            plex_aider.empty_trash(job.section_id)

    def start_forget(self, job: ModelBase) -> None:
        '''forget'''
        RcloneAider().vfs_forget(job.target, job.vfs)

    def start_startup(self, job: ModelBase) -> None:
        '''startup'''
        platform_name = platform.system().lower()
        LOGGER.debug(f'플랫폼: {platform_name}')
        if platform_name == 'windows':
            WindowsAider().startup()
        elif platform_name == 'linux':
            UbuntuAider().startup()
        else:
            LOGGER.warning(f'실행할 수 없는 OS 환경입니다: {platform_name}')

    def start_clear(self, job: ModelBase) -> None:
        '''clear'''
        PlexmateAider().clear_section(job.clear_section, job.clear_type, job.clear_level)

    def start_pm_ready_refresh(self, job: ModelBase) -> None:
        '''pm_ready_refresh'''
        plex_aider = PlexmateAider()
        # plexmate
        plex_aider.check_scanning(CONFIG.get_int(SETTING_PLEXMATE_MAX_SCAN_TIME))
        plex_aider.check_timeover(CONFIG.get(SETTING_PLEXMATE_TIMEOVER_RANGE))
        # refresh
        targets = {s.target for s in plex_aider.get_scan_items('READY')}
        if targets:
            for target in targets:
                RcloneAider().vfs_refresh(target, job.recursive, job.vfs)
        else:
            LOGGER.info(f'plex_mate: 새로고침 대상이 없습니다.')

    def start_scan(self, job: ModelBase) -> None:
        '''scan'''
        PlexmateAider().scan(job.scan_mode, job.target, job.periodic_id, job.section_id)

    def start_refresh(self, job: ModelBase) -> None:
        '''refresh'''
        rclone_aider = RcloneAider()
        # section_id DB 패치가 안 됐을 경우 대비
        if job.section_id and int(job.section_id) > 0:
            targets = PlexmateAider().get_targets(job.target, job.section_id)
            for location, _ in targets.items():
                rclone_aider.vfs_refresh(location, job.recursive, job.vfs)
        else:
            rclone_aider.vfs_refresh(job.target, job.recursive, job.vfs)

    def start_refresh_scan(self, job: ModelBase) -> None:
        '''refresh_scan'''
        # refresh
        plex_aider = PlexmateAider()
        rclone_aider = RcloneAider()
        if job.scan_mode == SCAN_MODE_KEYS[1] and job.periodic_id > 0:
            # 주기적 스캔 작업 새로고침
            targets = plex_aider.get_periodic_locations(job.periodic_id)
            for target in targets:
                rclone_aider.vfs_refresh(target, job.recursive, job.vfs)
            plex_aider.scan(job.scan_mode, periodic_id=job.periodic_id)
        else:
            targets = plex_aider.get_targets(job.target, job.section_id)
            for location, section_id in targets.items():
                rclone_aider.vfs_refresh(location, job.recursive, job.vfs)
                plex_aider.scan(job.scan_mode, location, section_id=section_id)


class SettingAider(Aider):

    def __init__(self) -> None:
        super().__init__()

    def remote_command(self, command: str, url: str, username: str, password: str) -> requests.Response:
        LOGGER.debug(url)
        return self.request('POST', f'{url}/{command}', auth=(username, password))

    def depends(self, text: str = None) -> str:
        try:
            if not DEPEND_USER_YAML.exists():
                shutil.copyfile(DEPEND_SOURCE_YAML, DEPEND_USER_YAML)
            if text:
                with DEPEND_USER_YAML.open(mode='w', encoding='utf-8', newline='\n') as file:
                    file.write(text)
                    depends = text
            else:
                with DEPEND_USER_YAML.open(encoding='utf-8', newline='\n') as file:
                    depends = file.read()
            return depends
        except:
            LOGGER.error(traceback.format_exc())
            if text: return text
            else:
                with DEPEND_SOURCE_YAML.open(encoding='utf-8', newline='\n') as file:
                    return file.read()


class BrowserAider(Aider):

    def __init__(self) -> None:
        super().__init__()

    def get_dir(self, target_path: str) -> list[dict[str, str]]:
        target_path = Path(target_path)
        with os.scandir(target_path) as scandirs:
            target_list = []
            for entry in scandirs:
                try:
                    target_list.append(self.pack_dir(entry))
                except Exception as e:
                    LOGGER.warning(e)
                    continue
            target_list = sorted(target_list, key=lambda entry: (entry.get('is_file'), entry.get('name')))
            parent_pack = self.pack_dir(target_path.parent)
            parent_pack['name'] = '..'
            target_list.insert(0, parent_pack)
            return target_list

    def pack_dir(self, entry: os.DirEntry | Path) -> dict[str, Any]:
        stats: os.stat_result = entry.stat(follow_symlinks=True)
        return {
            'name': entry.name,
            'path': entry.path if isinstance(entry, os.DirEntry) else str(entry),
            'is_file': entry.is_file(),
            'size': self.format_file_size(stats.st_size),
            'ctime': self.get_readable_time(stats.st_ctime),
            'mtime': self.get_readable_time(stats.st_mtime),
        }

    def format_file_size(self, size: int, decimals: int = 1, binary_system: bool = True) -> str:
        units = ['B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']
        largest_unit = 'Y'
        if binary_system:
            step = 1024
        else:
            step = 1000
        for unit in units:
            if size < step:
                return f'{size:.{decimals}f}{unit}'
            size /= step
        return f'{size:.{decimals}f}{largest_unit}'


class PluginAider(Aider):

    def __init__(self, name: str) -> None:
        super().__init__(name)

    @property
    def plugin(self):
        plugin = FRAMEWORK.PluginManager.get_plugin_instance(self.name)
        if plugin:
            return plugin
        else:
            raise Exception(f'플러그인을 찾을 수 없습니다: {self.name}')

    def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def check_plugin(func: callable) -> callable:
        @functools.wraps(func)
        def wrap(*args, **kwds):
            if args[0].plugin:
                return func(*args, **kwds)
            else:
                raise Exception(f'플러그인을 찾을 수 없습니다: {args[0].name}')
        return wrap

    @check_plugin
    def get_module(self, module: str) -> PluginModuleBase:
        return self.plugin.logic.get_module(module)


class PlexmateAider(PluginAider):

    def __init__(self) -> None:
        super().__init__('plex_mate')
        self.db = self.plugin.PlexDBHandle

    def get_scan_model(self) -> ModelBase:
        return self.get_module('scan').web_list_model

    def get_scan_items(self, status: str) -> list[ModelBase]:
        return self.get_scan_model().get_list_by_status(status)

    def get_sections(self) -> dict[str, Any]:
        return {
            SECTION_TYPE_KEYS[0]: [{'id': item['id'], 'name': item['name']} for item in self.db.library_sections(section_type=1)],
            SECTION_TYPE_KEYS[1]: [{'id': item['id'], 'name': item['name']} for item in self.db.library_sections(section_type=2)],
            SECTION_TYPE_KEYS[2]: [{'id': item['id'], 'name': item['name']} for item in self.db.library_sections(section_type=8)],
            SECTION_TYPE_KEYS[3]: [{'id': item['id'], 'name': item['name']} for item in self.db.library_sections(section_type=13)],
        }

    def get_periodics(self) -> list[dict[str, Any]]:
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

    def get_trashes(self, section_id: int, page_no: int = 1, limit: int = 10) -> dict[str, Any]:
        query = '''
        SELECT media_items.id, media_items.metadata_item_id, media_items.deleted_at, media_parts.file
        FROM media_parts, media_items
        WHERE media_items.deleted_at != ''
            AND media_items.library_section_id = {section_id}
            AND media_items.id = media_parts.media_item_id
        ORDER BY media_parts.file
        LIMIT {limit} OFFSET {offset}
        '''
        offset = (page_no - 1) * limit
        with sqlite3.connect(self.plugin.ModelSetting.get('base_path_db')) as con:
            con.row_factory = PluginAider.dict_factory
            cs = con.cursor()
            return cs.execute(query.format(section_id=section_id, limit=limit, offset=offset)).fetchall()

    def get_trash_list(self, section_id: int, page_no: int = 1, limit: int = 10) -> dict[str, Any]:
        result = {'total': 0, 'limit': limit, 'page': page_no, 'section_id': section_id, 'total_paths': 0, 'data': None}
        total_rows = self.get_trashes(section_id, 1, -1)
        paths ={Path(row['file']).parent for row in total_rows}
        result['total'] = len(total_rows)
        result['total_paths'] = len(paths)
        rows = self.get_trashes(section_id, page_no, limit)
        if len(rows) > 0:
            for row in rows:
                row['deleted_at'] = self.get_readable_time(row['deleted_at'])
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
        scans = self.get_scan_items('SCANNING')
        if scans:
            model = self.get_scan_model()
            for scan in scans:
                if int((datetime.now() - scan.process_start_time).total_seconds() / 60) >= max_scan_time:
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
        overs = self.get_scan_items('FINISH_TIMEOVER')
        if overs:
            start_id, end_id = list(map(int, item_range.split('~')))
            for over in overs:
                if over.id in range(start_id, end_id + 1):
                    LOGGER.warning(f'READY 로 상태 변경: {over.id} {over.target}')
                    over.set_status('READY', save=True)

    def get_targets(self, target: str, section_id: int = -1) -> dict[str, int]:
        mappings = self.parse_mappings(CONFIG.get(SETTING_PLEXMATE_PLEX_MAPPING))
        target = Path(self.update_path(target, mappings))
        # section_id DB 패치가 안 됐을 경우 대비
        if section_id and int(section_id) > 0:
            locations = self.db.select(f'SELECT library_section_id, root_path FROM section_locations WHERE library_section_id = {section_id}')
        else:
            locations = self.db.select('SELECT library_section_id, root_path FROM section_locations')
        targets = {}
        for location in locations:
            root = Path(f'{location["root_path"]}')
            if target.is_relative_to(root):
                targets[str(target)] = int(location['library_section_id'])
            elif root.is_relative_to(target):
                targets[str(root)] = int(location['library_section_id'])
        return targets

    def web_scan(self, section_id: int, location: str = None) -> None:
        '''
        웹 스캔의 activity 추적은 정확하지 않아 명령만 전달하는 방식으로 실행
        정확한 추적은 바이너리 스캔의 activity 옵션으로 가능해 보임
        '''
        url = f'{self.plugin.ModelSetting.get("base_url")}/library/sections/{section_id}/refresh'
        params = {
            'X-Plex-Token': self.plugin.ModelSetting.get('base_token'),
            'path': location,
        }
        section = self.get_section_by_id(section_id)
        try:
            response = self.request('GET', url, params=params)
            if str(response.status_code)[0] == '2':
                LOGGER.info(f'스캔 전송: {section.get("name")}: {location}')
            else:
                raise Exception(f'스캔 전송 실패: {response.text}')
        except:
            LOGGER.error(traceback.format_exc())


    def scan(self, scan_mode: str, target: str = None, periodic_id: int = -1, section_id: int = -1) -> None:
        if scan_mode == SCAN_MODE_KEYS[2]:
            targets = self.get_targets(target, section_id)
            if targets:
                LOGGER.debug(f'섹션 ID 검색 결과: {set(targets.values())}')
                for location, section_id in targets.items():
                    self.web_scan(section_id, location)
            else:
                LOGGER.error(f'섹션 ID를 찾을 수 없습니다: {target}')
        elif scan_mode == SCAN_MODE_KEYS[1]:
            module = self.get_module('periodic')
            scan_job = self.get_periodic_job(periodic_id)
            if scan_job:
                LOGGER.debug(f'주기적 스캔 작업 실행: {scan_job}')
                module.one_execute(periodic_id - 1)
        else:
            scan_item = self.get_scan_model()(target)
            scan_item.save()
            LOGGER.info(f'plex_mate 스캔 ID: {scan_item.id}')

    def get_locations_by_id(self, section_id: int) -> list[str]:
        return [location.get('root_path') for location in self.db.section_location(library_id=section_id)]

    def get_section_by_id(self, section_id: int) -> dict[str, Any]:
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
        try:
            response = self.request('PUT', url, params=params)
            if str(response.status_code)[0] == '2':
                LOGGER.info(f'휴지통 비우기 명령을 전송했습니다: {section.get("name")}')
            else:
                raise Exception(f'휴지통 비우기 명령을 전달할 수 없습니다: {response.text}')
        except Exception as e:
            LOGGER.error(traceback.format_exc())


class GDSToolAider(PluginAider):

    def __init__(self) -> None:
        super().__init__('gds_tool')

    def get_model(self, name: str) -> ModelBase:
        return self.get_module(name).web_list_model

    def get_total_records(self, name: str) -> int:
        with FRAMEWORK.app.app_context():
            return FRAMEWORK.db.session.query(self.get_model(name)).count()

    def delete(self, name: str, span: int) -> None:
        self.get_model(name).delete_all(span)
        with FRAMEWORK.app.app_context():
            db_file = FRAMEWORK.app.config['SQLALCHEMY_BINDS']['gds_tool'].replace('sqlite:///', '').split('?')[0]
            with sqlite3.connect(db_file) as conn:
                conn.row_factory = sqlite3.Row
                cs = conn.cursor()
                cs.execute(f'VACUUM;').fetchall()


class RcloneAider(Aider):

    def __init__(self) -> None:
        super().__init__()

    def get_metadata_cache(self, fs: str) -> tuple[int, int]:
        result = self.vfs_stats(fs).json().get("metadataCache")
        return result.get('dirs', 0), result.get('files', 0)

    def vfs_stats(self, fs: str) -> Response:
        return self.command("vfs/stats", data={"fs": fs})

    def command(self, command: str, data: dict = None) -> Response:
        LOGGER.debug(f'{command}: {data}')
        return self.request(
            "JSON",
            f'{CONFIG.get(SETTING_RCLONE_REMOTE_ADDR)}/{command}',
            data=data,
            auth=(CONFIG.get(SETTING_RCLONE_REMOTE_USER), CONFIG.get(SETTING_RCLONE_REMOTE_PASS))
        )

    def _vfs_refresh(self, remote_path: str, recursive: bool = False, fs: str = None, forget: bool = False) -> Response:
        data = {
            'fs': fs or CONFIG.get(SETTING_RCLONE_REMOTE_VFS),
            'dir': remote_path
        }
        if forget:
            cmd, title = 'vfs/forget', '캐시삭제 결과'
        else:
            cmd, title = 'vfs/refresh', '새로고침 결과'
            data['recursive'] = str(recursive).lower()
        start_dirs, start_files = self.get_metadata_cache(data["fs"])
        start = time.time()
        response = self.command(cmd, data=data)
        dirs, files = self.get_metadata_cache(data["fs"])
        try:
            content = response.json()
        except requests.exceptions.JSONDecodeError:
            content = response.text
        LOGGER.info(f'{title}: dirs={dirs - start_dirs} files={files - start_files} elapsed={(time.time() - start):.1f}s content={content}')
        return response

    def vfs_refresh(self, local_path: str, recursive: bool = False, fs: str = None) -> Response:
        # 이미 존재하는 파일이면 패스, 존재하지 않은 파일/폴더, 존재하는 폴더이면 진행
        local_path = Path(local_path)
        if local_path.is_file():
            response = requests.Response()
            response.status_code = 0
            reason = '이미 존재하는 파일입니다'
            response._content = bytes(reason, 'utf-8')
            LOGGER.debug(f'{reason}: {local_path}')
        else:
            # vfs/refresh 용 존재하는 경로 찾기
            test_dirs = [local_path]
            already_exists = test_dirs[0].exists()
            while not test_dirs[-1].exists():
                test_dirs.append(test_dirs[-1].parent)
            LOGGER.debug(f"경로 검사: {str(test_dirs)}")
            mappings = self.parse_mappings(CONFIG.get(SETTING_RCLONE_MAPPING))
            while test_dirs:
                # vfs/refresh 후
                response = self._vfs_refresh(self.update_path(str(test_dirs[-1]), mappings), recursive, fs)
                # 타겟이 존재하는지 점검
                if local_path.exists():
                    # 존재하지 않았던 폴더면 vfs/refresh
                    if not local_path.is_file() and not already_exists:
                        self._vfs_refresh(self.update_path(str(local_path), mappings), recursive, fs)
                        # 새로운 폴더를 새로고침 후 한번 더 타겟 경로 존재 점검
                        if not local_path.exists() and len(test_dirs) > 1: continue
                    break
                else:
                    result, reason = self.is_successful(response)
                    if not result:
                        LOGGER.error(f'새로고침 실패: {reason}: {test_dirs[-1]}')
                        break
                # 타겟이 아직 존재하지 않으면 다음 상위 경로로 시도
                test_dirs.pop()
        return response

    def vfs_forget(self, local_path: str, fs: str = None) -> Response:
        mappings = self.parse_mappings(CONFIG.get(SETTING_RCLONE_MAPPING))
        response = self._vfs_refresh(self.update_path(local_path, mappings), fs=fs, forget=True)
        result, reason = self.is_successful(response)
        if not result:
            LOGGER.error(f'캐시삭제 실패: {reason}: {local_path}')
        return response

    def is_successful(self, response: Response) -> tuple[bool, str]:
        if not str(response.status_code).startswith('2'):
            return False, f'status code: {response.status_code}, content: {response.text}'
        try:
            # {'error': '', ...}
            # {'result': {'/path/to': 'Invalid...'}}
            # {'result': {'/path/to': 'OK'}}
            # {'forgotten': ['/path/to']}
            _json = response.json()
            if _json.get('result'):
                result = list(_json.get('result').values())[0]
                return (True, result) if result == 'OK' else (False, result)
            elif _json.get('forgotten'):
                return True, _json.get('forgotten')
            else:
                return False, _json.get('error')
        except:
            LOGGER.error(traceback.format_exc())
            return False, response.text


class StatupAider(Aider):

    def __init__(self) -> None:
        super().__init__()

    def sub_run(self, *args: tuple[str],
                stdout: int = subprocess.PIPE, stderr: int = subprocess.STDOUT,
                encoding: str = locale.getpreferredencoding(),
                **kwds: dict[str, Any]) -> CompletedProcess:
        startup_executable = CONFIG.get(SETTING_STARTUP_EXECUTABLE)
        startup_executable = True if startup_executable.lower() == 'true' else False
        if not startup_executable:
            msg = f'실행이 허용되지 않았어요.'
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
        plugins_installed = [plugin_name for plugin_name in FRAMEWORK.PluginManager.all_package_list.keys()]
        depends = yaml.safe_load(SettingAider().depends()).get('dependencies')

        require_plugins, require_packages, require_commands = self.get_require_plugins(plugins_installed, depends)

        # 1. Commands from the setting
        executable_commands = CONFIG.get(SETTING_STARTUP_COMMANDS).splitlines()
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

    def execute(self, commands: list[str], require_plugins: set[str] = {}, depends: dict[str, Any] = {}) -> None:
        startup_executable = CONFIG.get(SETTING_STARTUP_EXECUTABLE)
        startup_executable = True if startup_executable.lower() == 'true' else False
        if startup_executable:
            for command in commands:
                command = shlex.split(command)
                result: CompletedProcess = self.sub_run(*command, timeout=CONFIG.get_int(SETTING_STARTUP_TIMEOUT))
                if result.returncode == 0:
                    msg = '성공'
                else:
                    msg = result.stdout
                LOGGER.info(f'실행 결과 {command}: {msg}')

            for plugin in require_plugins:
                result = FRAMEWORK.PluginManager.plugin_install(depends.get(plugin, {"repo": "NO INFO."}).get("repo"))
                LOGGER.info(result.get('msg'))
        else:
            LOGGER.warning(f'실행이 허용되지 않았어요.')

    def get_installed_plugins(self) -> list[str]:
        return [plugin_name for plugin_name in FRAMEWORK.PluginManager.all_package_list.keys()]

    def get_require_plugins(self, plugins_installed: list[str], depends) -> tuple[set, set, set]:
        require_plugins = set()
        require_packages = set()
        require_commands = set()
        # plugin by plugin
        for plugin in plugins_installed:
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


class UbuntuAider(StatupAider):

    def __init__(self) -> None:
        super().__init__()

    def get_commands_from_packages(self, require_packages) -> list[str]:
        return [f'apt-get install -y {req}' for req in require_packages]


class WindowsAider(StatupAider):

    def __init__(self) -> None:
        super().__init__()

    def get_commands_from_packages(self, require_packages) -> list[str]:
        LOGGER.warning(f'윈도우는 패키지 설치 명령어를 "commands" 혹은 "실행할 명령어"로 실행')
        return []
