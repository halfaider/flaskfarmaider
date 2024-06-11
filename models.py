import datetime
import traceback
import json

from flask.wrappers import Request
from flask_sqlalchemy.query import Query
from sqlalchemy import desc
from sqlalchemy.orm.attributes import InstrumentedAttribute

from .setup import ModelBase
from .setup import FRAMEWORK, PLUGIN, LOGGER, CONFIG
from .constants import *


class Job(ModelBase):

    P = PLUGIN
    __tablename__ = f'{PLUGIN.package_name}_jobs'
    __bind_key__ = PLUGIN.package_name

    id = FRAMEWORK.db.Column(FRAMEWORK.db.Integer, primary_key=True)
    ctime = FRAMEWORK.db.Column(FRAMEWORK.db.DateTime)
    ftime = FRAMEWORK.db.Column(FRAMEWORK.db.DateTime)
    desc = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    target = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    task = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    recursive = FRAMEWORK.db.Column(FRAMEWORK.db.Boolean)
    vfs = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    schedule_mode = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    schedule_interval = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    schedule_auto_start = FRAMEWORK.db.Column(FRAMEWORK.db.Boolean)
    status = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    scan_mode = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    periodic_id = FRAMEWORK.db.Column(FRAMEWORK.db.Integer)
    clear_type = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    clear_section = FRAMEWORK.db.Column(FRAMEWORK.db.Integer)
    clear_level = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    section_id = FRAMEWORK.db.Column(FRAMEWORK.db.Integer)
    # Column, type, default value
    formdata_mapping = {
        'sch-task': (task, task.type.python_type, TASK_KEYS[0]),
        'sch-description': (desc, desc.type.python_type, ''),
        'sch-schedule-mode': (schedule_mode, schedule_mode.type.python_type, FF_SCHEDULE_KEYS[0]),
        'sch-schedule-interval': (schedule_interval, schedule_interval.type.python_type, '60'),
        'sch-target-path': (target, target.type.python_type, ''),
        'sch-vfs': (vfs, vfs.type.python_type, ''),
        'sch-recursive': (recursive, recursive.type.python_type, False),
        'sch-recursive-select': (recursive, recursive.type.python_type, False),
        'sch-schedule-auto-start': (schedule_auto_start, schedule_auto_start.type.python_type, False),
        'sch-schedule-auto-start-select': (schedule_auto_start, schedule_auto_start.type.python_type, False),
        'sch-scan-mode': (scan_mode, scan_mode.type.python_type, SCAN_MODE_KEYS[0]),
        'sch-scan-mode-periodic-id': (periodic_id, periodic_id.type.python_type, -1),
        'sch-clear-type': (clear_type, clear_type.type.python_type, ''),
        'sch-clear-level': (clear_level, clear_level.type.python_type, ''),
        'sch-clear-section': (clear_section, clear_section.type.python_type, -1),
        'sch-target-section': (section_id, section_id.type.python_type, -1),
    }

    def __init__(self, task: str = '', schedule_mode: str = FF_SCHEDULE_KEYS[0], schedule_auto_start: bool = False,
                 desc: str = '', target: str = '', recursive: bool = False, section_id: int = -1,
                 vfs: str = '', scan_mode: str = SCAN_MODE_KEYS[0], periodic_id: int = -1,
                 clear_type: str = '', clear_level: str = '', clear_section: int = -1, schedule_interval = '60') -> None:
        self.ctime = datetime.datetime.now()
        self.ftime = datetime.datetime(1970, 1, 1)
        self.status = STATUS_KEYS[0]

        self.task = task
        self.schedule_mode = schedule_mode
        self.schedule_auto_start = schedule_auto_start
        self.schedule_interval = schedule_interval
        self.desc = desc
        self.target = target
        self.recursive = recursive
        self.vfs = vfs
        self.scan_mode = scan_mode
        self.periodic_id = periodic_id
        self.clear_type = clear_type
        self.clear_level = clear_level
        self.clear_section = clear_section
        self.section_id = section_id

    def as_dict(self) -> dict:
        '''override'''
        return super().as_dict()

    def save(self) -> None:
        '''override'''
        super().save()

    @classmethod
    def get_paging_info(cls, count: int, current_page: int, page_size: int) -> dict | None:
        '''override'''
        return super().get_paging_info(count, current_page, page_size)

    @classmethod
    def get_by_id(cls, id) -> ModelBase:
        '''override'''
        return super().get_by_id(id)

    @classmethod
    def get_list(cls, by_dict: bool = False) -> list | None:
        '''override'''
        return super().get_list(by_dict)

    @classmethod
    def delete_by_id(cls, id: int) -> bool:
        '''override'''
        return super().delete_by_id(id)

    @classmethod
    def delete_all(cls, day: int | str | None = None) -> int:
        '''override'''
        return super().delete_all(day)

    @classmethod
    def make_query_search(cls, query: Query, search: str, field: InstrumentedAttribute) -> Query:
        '''override'''
        return super().make_query_search(query, search, field)

    def update(self, data: dict[str, str | int | bool]) -> ModelBase:
        for k, v in data.items():
            try:
                setattr(self, k, v)
            except:
                LOGGER.error(traceback.format_exc())
        return self

    @classmethod
    def update_formdata(cls, job_id: int, formdata: dict[str, list]) -> ModelBase:
        if job_id > 0:
            model = cls.get_by_id(job_id)
        else:
            model = Job()

        if formdata.get('sch-task', [-1])[0] == TASK_KEYS[5]:
            formdata.update({'sch-schedule-interval': ['매 시작']})

        for key in ['sch-recursive', 'sch-recursive-select', 'sch-schedule-auto-start', 'sch-schedule-auto-start-select']:
            val = formdata.get(key)
            if val:
                formdata[key] = [val[0].lower() == 'true']

        data = {}
        for k, v in formdata.items():
            try:
                mapping = model.formdata_mapping.get(k)
                data[mapping[0].name] = mapping[1](v[0])
            except:
                LOGGER.error(f'formdata key: {k}')
                LOGGER.error(traceback.format_exc())

        model.update(data)
        model.save()
        return model

    @classmethod
    def get_job(cls, id: int = -1, info: dict = None) -> ModelBase:
        if id > 0:
            job = cls.get_by_id(id)
        elif info:
            job = Job().update(info)
        else:
            job = Job()
            job.id = id
        return job

    @classmethod
    def make_query(cls, request: Request, order: str = 'desc', keyword: str = '', option1: str = SEARCH_KEYS[0], option2: str = 'all') -> Query:
        '''override'''
        with FRAMEWORK.app.app_context():
            query = cls.make_query_search(FRAMEWORK.db.session.query(cls), keyword, getattr(cls, option1))
            if option2 != 'all':
                query = query.filter(getattr(cls, option1) == option2)
            if order in ['desc', 'asc']:
                query = query.order_by(desc(cls.id) if order == 'desc' else cls.id)
            else:
                query = query.order_by(desc(getattr(cls, order)))
            return query

    def set_status(self, status: str, save: bool = True) -> ModelBase:
        if status in STATUS_KEYS:
            self.status = status
            if status == STATUS_KEYS[2]:
                self.ftime = datetime.datetime.now()
                self.status = STATUS_KEYS[0]
            if save:
                self.save()
        else:
            LOGGER.error(f'wrong status: {status}')
        return self

    @classmethod
    def web_list(cls, request: Request) -> dict:
        '''override'''
        data = {}
        data['list'] = []
        opt_page = int(request.form.get('page') or 1 )
        page_size = int(request.form.get('length') or 30)
        opt_order = request.form.get('order', 'desc')
        opt_option1 = request.form.get('option1', SEARCH_KEYS[0])
        opt_option2 = request.form.get('option2', 'all')
        opt_keyword = request.form.get('keyword')
        try:
            sch_mod = PLUGIN.logic.get_module(SCHEDULE)
            query = cls.make_query(request, opt_order, opt_keyword, opt_option1, opt_option2)
            total = query.count()
            query = query.limit(page_size).offset((opt_page - 1) * page_size)
            for row in query.all():
                item = row.as_dict()
                sch_id = sch_mod.create_schedule_id(item['id'])
                item['is_include'] = FRAMEWORK.scheduler.is_include(sch_id)
                item['is_running'] = FRAMEWORK.scheduler.is_running(sch_id)
                data['list'].append(item)
            data['paging'] = cls.get_paging_info(total, opt_page, page_size)
            CONFIG.set(f'{SCHEDULE}_last_list_option', f'{opt_order}|{opt_page}|{page_size}|{opt_keyword or ""}|{opt_option1 or ""}|{opt_option2 or ""}')
        except:
            LOGGER.error(traceback.format_exc())
        finally:
            return data


class Watch(ModelBase):

    P = PLUGIN
    __tablename__ = f'{PLUGIN.package_name}_watches'
    __bind_key__ = PLUGIN.package_name

    id = FRAMEWORK.db.Column(FRAMEWORK.db.Integer, primary_key=True)
    observer = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    timeout = FRAMEWORK.db.Column(FRAMEWORK.db.Integer)

    enable = FRAMEWORK.db.Column(FRAMEWORK.db.Boolean)
    ignore_directory = FRAMEWORK.db.Column(FRAMEWORK.db.Boolean)
    case_sensitive = FRAMEWORK.db.Column(FRAMEWORK.db.Boolean)
    recursive = FRAMEWORK.db.Column(FRAMEWORK.db.Boolean)

    paths = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    events = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    events_interval = FRAMEWORK.db.Column(FRAMEWORK.db.Integer)
    patterns = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    ignore_patterns = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    mappings = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    conduits = FRAMEWORK.db.Column(FRAMEWORK.db.String)

    status = FRAMEWORK.db.Column(FRAMEWORK.db.String)
    description = FRAMEWORK.db.Column(FRAMEWORK.db.String)

    # Column, type, default value
    formdata_mapping = {
        'watch-observer': (observer, observer.type.python_type, 'auto'),
        'watch-timeout': (timeout, timeout.type.python_type, 60),

        'watch-enable': (enable, enable.type.python_type, False),
        'watch-ignore-directory': (ignore_directory, ignore_directory.type.python_type, False),
        'watch-case-sensitive': (case_sensitive, case_sensitive.type.python_type, True),
        'watch-recursive': (recursive, recursive.type.python_type, False),

        'watch-paths': (paths, paths.type.python_type, '[]'),
        'watch-events': (events, events.type.python_type, '["created", "deleted", "moved", "modified", "opened", "closed"]'),
        'watch-events-interval': (events_interval, events_interval.type.python_type, 2),
        'watch-patterns': (patterns, patterns.type.python_type, '["*"]'),
        'watch-ignore-patterns': (ignore_patterns, ignore_patterns.type.python_type, '[]'),
        'watch-mappings': (mappings, mappings.type.python_type, '[]'),
        'watch-conduits': (conduits, conduits.type.python_type, '{}'),

        'watch-status': (status, status.type.python_type, STATUS_KEYS[0]),
        'watch-description': (description, description.type.python_type, ''),
    }

    @classmethod
    def make_query(cls, request: Request, order: str = 'desc', keyword: str = '', option1: str = 'observer', option2: str = 'all') -> Query:
        '''override'''
        with FRAMEWORK.app.app_context():
            query = cls.make_query_search(FRAMEWORK.db.session.query(cls), keyword, getattr(cls, option1))
            if option2 != 'all':
                query = query.filter(getattr(cls, option1) == option2)
            if order in ['desc', 'asc']:
                query = query.order_by(desc(cls.id) if order == 'desc' else cls.id)
            else:
                query = query.order_by(desc(getattr(cls, order)))
            return query

    @classmethod
    def web_list(cls, request: Request) -> dict:
        '''override'''
        data = {}
        data['list'] = []
        opt_page = int(request.form.get('page') or 1 )
        page_size = int(request.form.get('length') or 30)
        opt_order = request.form.get('order', 'desc')
        opt_option1 = request.form.get('option1', 'observer')
        opt_option2 = request.form.get('option2', 'all')
        opt_keyword = request.form.get('keyword')
        try:
            query = cls.make_query(request, opt_order, opt_keyword, opt_option1, opt_option2)
            total = query.count()
            query = query.limit(page_size).offset((opt_page - 1) * page_size)
            data['list'] = [row.as_dict() for row in query.all()]
            data['paging'] = cls.get_paging_info(total, opt_page, page_size)
            CONFIG.set(f'watcher_last_list_option', f'{opt_order}|{opt_page}|{page_size}|{opt_keyword or ""}|{opt_option1 or ""}|{opt_option2 or ""}')
        except:
            LOGGER.error(traceback.format_exc())
        finally:
            return data

    @classmethod
    def get_model(cls, id: int = -1, data: dict = None) -> ModelBase:
        if id > 0:
            model = cls.get_by_id(id)
        elif data:
            model = cls().update(data)
        else:
            model = cls()
            model.id = id
        return model

    def update(self, data: dict[str, str | int | bool]) -> ModelBase:
        for k, v in data.items():
            try:
                setattr(self, k, v)
            except:
                LOGGER.error(traceback.format_exc())
        return self

    @classmethod
    def update_formdata(cls, model_id: int, formdata: dict[str, list]) -> ModelBase:
        if model_id > 0:
            model = cls.get_by_id(model_id)
        else:
            model = cls()

        for key in ['watch-paths', 'watch-patterns', 'watch-ignore-patterns', 'watch-mappings']:
            val = formdata.get(key)
            if val:
                formdata[key] = [json.dumps(val[0].splitlines())]

        # check boxes
        for key in [
                    'watch-ignore-directory',
                    'watch-case-sensitive',
                    'watch-recursive',
                    'watch-enable',
                    'watch-events-created',
                    'watch-events-deleted',
                    'watch-events-moved',
                    'watch-events-modified',
                    'watch-events-opened',
                    'watch-events-closed',
                    'watch-conduits-shell',
                    'watch-conduits-rclone',
                    'watch-conduits-plex_mate',
                    'watch-conduits-plex',
                ]:
            val = formdata.get(key)
            if val:
                formdata[key] = [(val[0].lower() == 'true' or val[0].lower() == 'on')]

        events = set()
        for _event in {'created', 'deleted', 'moved', 'modified', 'opened', 'closed'}:
            if formdata.pop(f'watch-events-{_event}', [False])[0]:
                events.add(_event)
        if events:
            formdata['watch-events'] = [json.dumps(events)]
        conduits = {}
        for conduit in {'shell', 'rclone', 'plex', 'plex_mate'}:
            if formdata.pop(f'watch-conduits-{conduit}', [False])[0]:
                conduits[conduit] = {}
                priority = formdata.pop(f'watch-conduits-{conduit}-priority', None)
                mappings = formdata.pop(f'watch-conduits-{conduit}-mappings', None)
                if priority:
                    conduits[conduit]['priority'] = priority[0]
                if mappings:
                    conduits[conduit]['mappings'] = mappings[0].splitlines()
                if conduit == 'shell':
                    command = formdata.pop(f'watch-conduits-shell-command', None)
                    if command:
                        conduits[conduit]['command'] = command[0]
                elif conduit == 'rclone':
                    vfs = formdata.pop(f'watch-conduits-rclone-vfs', None)
                    if vfs:
                        conduits[conduit]['vfs'] = vfs[0]
            else:
                for key in list(formdata.keys()):
                    if f'watch-conduits-{conduit}-' in key:
                        formdata.pop(key)
        if conduits:
            formdata['watch-conduits'] = [json.dumps(conduits)]

        data = {}
        for k, v in formdata.items():
            try:
                mapping = cls.formdata_mapping.get(k)
                data[mapping[0].name] = mapping[1](v[0])
            except:
                LOGGER.error(f'formdata key: {k}')
                LOGGER.error(traceback.format_exc())
        PLUGIN.logger.debug(data)
        model.update(data)
        model.save()
        return model
