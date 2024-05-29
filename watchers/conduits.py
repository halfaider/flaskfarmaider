import time
import pathlib
import functools
import logging
import traceback
from typing import Optional, Union, Any

from utils import request, parse_mappings, map_path, parse_json_response, trace_event


logger = logging.getLogger(__name__)


class ConduitBase:

    def __init__(self, name: str, events: list, priority: int) -> None:
        self.name = name
        self.events = events
        self.priority = priority

    def flow(self, event: dict[str, Union[str, bool]]) -> None:
        raise Exception('You must override this method.')


class DummyConduit(ConduitBase):

    @trace_event
    def flow(self, event: dict[str, Union[str, bool]]) -> None:
        '''override'''


class RcloneConduit(ConduitBase):

    def __init__(self, *args: tuple,
                 rc_url: str,
                 rc_user: Optional[str] = None,
                 rc_pass: Optional[str] = None,
                 vfs: Optional[str] = None,
                 mappings: Optional[str] = None) -> None:
        super(RcloneConduit, self).__init__(*args)
        self.rc_url = rc_url
        self.rc_user = rc_user
        self.rc_pass = rc_pass
        self.vfs = vfs
        self.mappings: dict = parse_mappings(mappings)

    def flow(self, event: dict[str, Union[str, bool]]) -> None:
        '''override'''
        target =  event.get('dest_path') if event.get('event_type') == 'moved' else event.get('src_path')
        self.refresh(target, event.get('is_directory'))

    def command(method: callable) -> callable:
        @functools.wraps(method)
        def wrapper(self, *args: tuple, **kwds: dict) -> dict[str, Any]:
            command = '/'.join(method.__name__.split('__'))
            data: dict = method(self, *args, **kwds)
            logger.debug(f'{command}: {data}')
            # {'error': '', ...}
            # {'result': {'/path/to': 'Invalid...'}}
            # {'result': {'/path/to': 'OK'}}
            # {'forgotten': ['/path/to']}
            return parse_json_response(request("JSON", f'{self.rc_url}/{command}', data=data, auth=(self.rc_user, self.rc_pass)))
        return wrapper

    def get_metadata_cache(self) -> tuple[int, int]:
        result = self.vfs__stats(self.vfs).get("metadataCache", {})
        if not result:
            logger.error(f'No metadata cache statistics, assumed 0...')
        return result.get('dirs', 0), result.get('files', 0)

    @command
    def vfs__stats(self, fs: str) -> dict[str, Any]:
        return {'fs': fs}

    @command
    def vfs__refresh(self, remote_path: str, fs: str, recursive: bool = False) -> dict[str, Any]:
        return {
            'fs': fs,
            'dir': remote_path,
            'recursive': str(recursive).lower()
        }

    @command
    def operations__stat(self, remote_path: str, fs: str, opts: Optional[dict] = None) -> dict[str, Any]:
        data = {
            'fs': fs,
            'remote': remote_path,
        }
        if opts:
            data['opt'] = opts
        return data

    def is_file(self, remote_path: str) -> bool:
        result: dict = self.operations__stat(remote_path, self.vfs)
        logger.debug(result)
        item = result.get('item', {})
        return (item.get('IsDir').lower() == 'true') if item else False

    def _refresh(self, remote_path: str, fs: str, recursive: bool = False) -> dict[str, Any]:
        start_dirs, start_files = self.get_metadata_cache()
        start = time.time()
        result: dict = self.vfs__refresh(remote_path, fs, recursive)
        elapsed = time.time() - start
        dirs, files = self.get_metadata_cache()
        logger.info(f'dirs={dirs - start_dirs} files={files - start_files} elapsed={elapsed:.1f}s result="{result.get("result")!r}"')
        return result

    def refresh(self, local_path: str, is_directory: bool = False) -> None:
        to_be_tested = map_path(local_path, self.mappings)
        to_be_tested = pathlib.Path(to_be_tested)
        parent = to_be_tested.parent
        not_exist_dirs = []

        if not is_directory:
            to_be_tested = parent
            parent = to_be_tested.parent

        result = self._refresh(str(to_be_tested), self.vfs)
        # 파일 경로로 요청시: invalid argument
        while result['result'].get(str(to_be_tested)) == 'file does not exist':
            not_exist_dirs.insert(0, str(to_be_tested))
            to_be_tested = parent
            parent = to_be_tested.parent
            result = self._refresh(str(to_be_tested), self.vfs)
            if str(to_be_tested) == str(parent):
                logger.warning(f'Hit the top-level path...')
                break

        if not_exist_dirs:
            for dir in not_exist_dirs:
                result = self._refresh(dir, self.vfs)
                if not result.get(to_be_tested) == 'OK':
                    logger.error(f'Could not refresh: "{local_path}" result="{result["result"]!r}"')
                    break


class FFConduit(ConduitBase):

    def __init__(self, *args, ff_url: str, ff_apikey: Optional[str] = None) -> None:
        super(FFConduit, self).__init__(*args)
        self.ff_url = ff_url
        self.ff_apikey = ff_apikey

    def flow(self, event: dict[str, Union[str, bool]]) -> None:
        '''override'''
        raise Exception('You must override this method.')

    def api(package) -> callable:
        def decorator(method) -> callable:
            @functools.wraps(method)
            def wrapper(self, *args: tuple, **kwds: dict) -> dict[str, Any]:
                command = f'{package}/api/' + '/'.join(method.__name__.split('__'))
                data: dict = method(self, *args, **kwds)
                data['apikey'] = self.ff_apikey
                logger.debug(f'{command}: {data}')
                return parse_json_response(request('POST', f'{self.ff_url}/{command}', data=data))
            return wrapper
        return decorator


class PlexmateConduit(FFConduit):

    PACKAGE = 'plex_mate'

    def __init__(self, *args, mappings: str = None, **kwds) -> None:
        super(PlexmateConduit, self).__init__(*args, **kwds)
        self.mappings: dict = parse_mappings(mappings)

    def flow(self, event: dict[str, Union[str, bool]]) -> None:
        '''override'''
        if not event['is_directory']:
            self.scan(event['src_path'])

    def scan(self, local_path: str) -> None:
        logger.info(f'{self.scan__do_scan(map_path(local_path, self.mappings))}')

    @FFConduit.api(PACKAGE)
    def scan__do_scan(self, dir: str) -> dict:
        return {
            'target': dir,
            'mode': 'ADD'
        }
