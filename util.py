import sqlite3
import logging
import pathlib
import datetime
import os
import traceback
from typing import Any
from threading import Thread

import flask
import requests


logger = logging.getLogger(__name__)


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


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d


def get_rotating_file_logger(path: str,
                             name: str = None,
                             fmt: logging.Formatter = logging.Formatter(u'[%(asctime)s] %(message)s'),
                             max_bytes: int = 5 * 1024 * 1024,
                             level: int = logging.DEBUG) -> logging.Logger:
    log_file = pathlib.Path(path)
    if not name:
        name = log_file.name
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.handlers.RotatingFileHandler(filename=log_file, maxBytes=max_bytes, backupCount=5, encoding='utf8', delay=True)
        handler.setFormatter(fmt)
        handler.setLevel(level)
        logger.addHandler(handler)
    return logger


def get_readable_time(_time: float) -> str:
    return datetime.datetime.fromtimestamp(_time, datetime.timezone.utc).strftime('%b %d %H:%M')


def parse_mappings(settings: str | list) -> dict[str, str]:
    if type(settings) is str:
        settings = settings.splitlines()
    return _parse_mappings(settings)


def _parse_mappings(settings: list) -> dict[str, str]:
    mappings = {}
    for setting in settings:
        source, target = setting.rsplit(':', 1)
        mappings[source.strip()] = target.strip()
    return mappings


def update_path(target: str, mappings: dict) -> str:
    # 윈도우 경로 변경시
    if '\\' in target:
        target = target.replace('\\', '/')
    for k, v in mappings.items():
        target = target.replace(k, v)
    if not target:
        target = '/'
    return target


def get_dir(target_path: str) -> list[dict[str, str]]:
    target_path = pathlib.Path(target_path)
    with os.scandir(target_path) as scandirs:
        target_list = []
        for entry in scandirs:
            try:
                target_list.append(pack_dir(entry))
            except Exception as e:
                logger.warning(e)
        target_list = sorted(target_list, key=lambda entry: (entry.get('is_file'), entry.get('name')))
        parent_pack = pack_dir(target_path.parent)
        parent_pack['name'] = '..'
        target_list.insert(0, parent_pack)
        return target_list


def pack_dir(entry: os.DirEntry | pathlib.Path) -> dict:
    stats: os.stat_result = entry.stat(follow_symlinks=True)
    return {
        'name': entry.name,
        'path': entry.path if isinstance(entry, os.DirEntry) else str(entry),
        'is_file': entry.is_file(),
        'size': format_file_size(stats.st_size),
        'ctime': get_readable_time(stats.st_ctime),
        'mtime': get_readable_time(stats.st_mtime),
    }


def format_file_size(size: int, decimals: int = 1, binary_system: bool = True) -> str:
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


def get_client_ip(request: flask.Request) -> str:
    try:
        if 'X-Real-Ip' in request.headers:
            remote_addr = request.headers.getlist("X-Real-IP")[0].rpartition(' ')[-1]
        if 'X-Forwarded-For' in request.headers:
            remote_addr = request.headers.getlist("X-Forwarded-For")[0].rpartition(' ')[-1]
        else:
            remote_addr = request.remote_addr or 'unknown'
    except:
        logger.error(traceback.format_exc())
        remote_addr = 'unknown'
    return remote_addr


def parse_json_response(response: requests.Response) -> dict[str, Any]:
        try:
            # {'error': '', ...}
            # {'result': {'/path/to': 'Invalid...'}}
            # {'result': {'/path/to': 'OK'}}
            # {'forgotten': ['/path/to']}
            result = response.json()
        except Exception as e:
            result = {
                'status_code': response.status_code,
                'content': response.text.strip(),
                'error': f'{repr(e)}',
            }
        return result
