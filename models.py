import datetime
import traceback

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

    def __init__(self, task: str = '', schedule_mode: str = FF_SCHEDULE_KEYS[0], schedule_auto_start: bool = False,
                 desc: str = '', target: str = '', recursive: bool = False, section_id: int = -1,
                 vfs: str = '', scan_mode: str = SCAN_MODE_KEYS[0], periodic_id: int = -1,
                 clear_type: str = '', clear_level: str = '', clear_section: int = -1) -> None:
        self.ctime = datetime.datetime.now()
        self.ftime = datetime.datetime(1970, 1, 1)
        self.task = task
        self.schedule_mode = schedule_mode
        self.schedule_auto_start = schedule_auto_start
        self.desc = desc
        self.target = target
        self.recursive = recursive
        self.vfs = vfs
        self.status = STATUS_KEYS[0]
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
    def get_by_id(cls, id) -> 'Job':
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

    def update(self, info: dict) -> 'Job':
        self.task = info.get('task', self.task)
        self.schedule_mode = info.get('schedule_mode', self.schedule_mode)
        self.schedule_auto_start = info.get('schedule_auto_start', self.schedule_auto_start)
        self.desc = info.get('desc', self.desc)
        self.target = info.get('target', self.target)
        self.recursive = info.get('recursive', self.recursive)
        self.vfs = info.get('vfs', self.vfs)
        self.scan_mode = info.get('scan_mode', self.scan_mode)
        self.periodic_id = info.get('periodic_id', self.periodic_id)
        self.clear_type = info.get('clear_type', self.clear_type)
        self.clear_level = info.get('clear_level', self.clear_level)
        self.clear_section = info.get('clear_section', self.clear_section)
        self.section_id = info.get('section_id', self.section_id)
        return self

    @classmethod
    def update_formdata(cls, formdata: dict[str, list]) -> 'Job':
        _id = int(formdata.get('id')[0]) if formdata.get('id') else -1
        if _id == -1:
            model = Job()
        else:
            model = cls.get_by_id(_id)
        try:
            model.task = formdata.get('sch-task')[0] if formdata.get('sch-task') else TASK_KEYS[0]
            desc = formdata.get('sch-description')[0] if formdata.get('sch-description') else ''
            model.desc = desc or TASKS[model.task]["name"]
            model.schedule_mode = formdata.get('sch-schedule-mode')[0] if formdata.get('sch-schedule-mode') else FF_SCHEDULE_KEYS[0]
            model.schedule_interval = formdata.get('sch-schedule-interval')[0] if formdata.get('sch-schedule-interval') else '60'
            if model.task == TASK_KEYS[5]:
                model.target = ''
                model.schedule_interval = '매 시작'
            elif model.task == TASK_KEYS[3]:
                model.target = ''
            else :
                model.target = formdata.get('sch-target-path')[0] if formdata.get('sch-target-path') else '/'
            model.vfs = formdata.get('sch-vfs')[0] if formdata.get('sch-vfs') else 'remote:'
            recursive = formdata.get('sch-recursive')[0] if formdata.get('sch-recursive') else 'false'
            model.recursive = True if recursive.lower() == 'true' else False
            schedule_auto_start = formdata.get('sch-schedule-auto-start')[0] if formdata.get('sch-schedule-auto-start') else 'false'
            model.schedule_auto_start = True if schedule_auto_start.lower() == 'true' else False
            model.scan_mode = formdata.get('sch-scan-mode')[0] if formdata.get('sch-scan-mode') else SCAN_MODE_KEYS[0]
            model.periodic_id = int(formdata.get('sch-scan-mode-periodic-id')[0]) if formdata.get('sch-scan-mode-periodic-id') else -1
            model.clear_type = formdata.get('sch-clear-type')[0] if formdata.get('sch-clear-type') else ''
            model.clear_level = formdata.get('sch-clear-level')[0] if formdata.get('sch-clear-level') else ''
            model.clear_section = int(formdata.get('sch-clear-section')[0]) if formdata.get('sch-clear-section') else -1
            model.section_id = int(formdata.get('sch-target-section')[0]) if formdata.get('sch-target-section') else -1

            model.save()
        except:
            LOGGER.error(traceback.format_exc())
            LOGGER.error('작업을 저장하지 못했습니다.')
        finally:
            return model

    @classmethod
    def get_job(cls, id: int = -1, info: dict = None) -> 'Job':
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

    def set_status(self, status: str, save: bool = True) -> 'Job':
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
        page_size = 30
        data = {}
        data['list'] = []
        opt_page = int(request.form.get('page')) or 1
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
                item['is_include'] = True if FRAMEWORK.scheduler.is_include(sch_id) else False
                item['is_running'] = True if FRAMEWORK.scheduler.is_running(sch_id) else False
                data['list'].append(item)
            data['paging'] = cls.get_paging_info(total, opt_page, page_size)
            CONFIG.set(f'{SCHEDULE}_last_list_option', f'{opt_order}|{opt_page}|{opt_keyword or ""}|{opt_option1 or ""}|{opt_option2 or ""}')
        except:
            LOGGER.error(traceback.format_exc())
        finally:
            return data
