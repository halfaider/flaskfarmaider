import traceback
import logging
import functools
import re
import subprocess
import sys
from typing import Any, Optional, Union, Iterable
from logging.config import dictConfig

try:
    __import__('requests')
except:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-U', 'requests'])

import requests


logger = logging.getLogger(__name__)


class RedactedFormatter(logging.Formatter):

    def __init__(self, *args, patterns: Iterable = [], **kwds):
        super(RedactedFormatter, self).__init__(*args, **kwds)
        self.patterns = []
        for pattern in patterns:
            self.patterns.append(re.compile(pattern))

    def format(self, record):
        msg = super().format(record)
        for pattern in self.patterns:
            match = pattern.search(msg)
            if match:
                if len(match.groups()) > 0:
                    groups = list(match.groups())
                else:
                    groups = [match.group(0)]
                for found in groups:
                    msg = self.redact(re.compile(found), msg)
        return msg

    def redact(self, pattern: re.Pattern, text: str) -> str:
        return pattern.sub('<REDACTED>', text)


def set_logger(log_config: dict) -> None:
    filename = log_config['handlers']['default_file_handler']['filename']
    if not filename:
        log_config['handlers'].pop('default_file_handler', None)
    for config in log_config['loggers'].values():
        if not filename and 'default_file_handler' in config['handlers']:
            config['handlers'].remove('default_file_handler')
        elif filename and 'default_file_handler' not in config['handlers']:
            config['handlers'].append('default_file_handler')
    dictConfig(log_config)
    logger.info('logging config is loaded.')


def request(method: str, url: str, data: Optional[dict] = None, timeout: Union[int, tuple, None] = None, **kwds: dict) -> requests.Response:
    try:
        if method.upper() == 'JSON':
            return requests.request('POST', url, json=data or {}, timeout=timeout, **kwds)
        else:
            return requests.request(method, url, data=data, timeout=timeout, **kwds)
    except:
        tb = traceback.format_exc()
        logger.error(tb)
        response = requests.Response()
        response._content = bytes(tb, 'utf-8')
        response.status_code = 0
        return response


def parse_mappings(text: str) -> dict[str, str]:
    mappings = {}
    if text:
        settings = text.splitlines()
        for setting in settings:
            source, target = setting.split(':')
            mappings[source.strip()] = target.strip()
    return mappings


def map_path(target: str, mappings: dict) -> str:
    for k, v in mappings.items():
        target = target.replace(k, v)
    return target


def parse_json_response(response: requests.Response) -> dict[str, Any]:
    try:
        result = response.json()
    except Exception as e:
        result = {'result': response.text.strip()}
        logger.error(f'{repr(e)}: {response.text.strip()!r}')
    return result


def trace_event(func: callable) -> callable:
    @functools.wraps(func)
    def wrap(self, event):
        logger.debug(f"{self.name}.{func.__name__}(): event={event['event_type']} path={event['src_path']!r}")
        return func(self, event)
    return wrap
