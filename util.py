import sqlite3
import logging
import pathlib
from threading import Thread

from .setup import FRAMEWORK


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


def celery_is_active() -> bool:
    try:
        return True if FRAMEWORK.celery.control.inspect().stats() else False
    except:
        return False


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