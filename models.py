from datetime import datetime
import traceback
from typing import Any

from werkzeug.local import LocalProxy # type: ignore
from flask_sqlalchemy.query import Query # type: ignore
from sqlalchemy import desc # type: ignore

from plugin.model_base import ModelBase # type: ignore

from .setup import P, F, SCHEDULE


TASK_KEYS = ('refresh', 'scan', 'startup', 'pm_scan', 'pm_ready_refresh', 'refresh_pm_scan', 'refresh_pm_periodic', 'refresh_scan')
TASKS = {
    TASK_KEYS[0]: {'key': TASK_KEYS[0], 'name': '새로고침', 'desc': 'Rclone 리모트 콘트롤 서버에 vfs/refresh 요청', 'enable': False},
    TASK_KEYS[1]: {'key': TASK_KEYS[1], 'name': '스캔', 'desc': 'Plex Web API로 스캔 요청', 'enable': False},
    TASK_KEYS[2]: {'key': TASK_KEYS[2], 'name': '시작 스크립트', 'desc': 'Flaskfarm 시작시 필요한 OS 명령어를 실행', 'enable': False},
    TASK_KEYS[3]: {'key': TASK_KEYS[3], 'name': 'Plexmate 스캔', 'desc': 'Plexmate로 스캔 요청', 'enable': False},
    TASK_KEYS[4]: {'key': TASK_KEYS[4], 'name': 'Plexmate Ready 새로고침', 'desc': 'Plexmate의 READY 상태인 항목을 Rclone 리모트 콘트롤 서버에 vfs/refresh 요청', 'enable': False},
    TASK_KEYS[5]: {'key': TASK_KEYS[5], 'name': '새로고침 후 Plexmate 스캔', 'desc': 'Rclone 리모트 콘트롤 서버에 vfs/refresh 요청 후 Plexmate에 스캔 요청', 'enable': False},
    TASK_KEYS[6]: {'key': TASK_KEYS[6], 'name': '새로고침 후 주기적 스캔', 'desc': 'Rclone 리모트 콘트롤 서버에 vfs/refresh 요청 후 Plexmate의 주기적 스캔 작업 실행', 'enable': False},
    TASK_KEYS[7]: {'key': TASK_KEYS[7], 'name': '새로고침 후 스캔', 'desc': 'Rclone 리모트 콘트롤 서버에 vfs/refresh 요청 후 Plex Web API로 스캔 요청', 'enable': False},
}

STATUS_KEYS = ('ready', 'running', 'finish')
STATUSES = {
    STATUS_KEYS[0]: {'key': STATUS_KEYS[0], 'name': '대기중', 'desc': None},
    STATUS_KEYS[1]: {'key': STATUS_KEYS[1], 'name': '실행중', 'desc': None},
    STATUS_KEYS[2]: {'key': STATUS_KEYS[2], 'name': '완료', 'desc': None},
}

FF_SCHEDULE_KEYS = ('none', 'startup', 'schedule')
FF_SCHEDULES = {
    FF_SCHEDULE_KEYS[0]: {'key': FF_SCHEDULE_KEYS[0], 'name': '없음', 'desc': None},
    FF_SCHEDULE_KEYS[1]: {'key': FF_SCHEDULE_KEYS[1], 'name': '시작시 실행', 'desc': None},
    FF_SCHEDULE_KEYS[2]: {'key': FF_SCHEDULE_KEYS[2], 'name': '시간 간격', 'desc': None},
}


class Job(ModelBase):

    P = P
    __tablename__ = 'job'
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = P.package_name

    id = F.db.Column(F.db.Integer, primary_key=True)
    ctime = F.db.Column(F.db.DateTime)
    ftime = F.db.Column(F.db.DateTime)
    desc = F.db.Column(F.db.String)
    target = F.db.Column(F.db.String)
    task = F.db.Column(F.db.String)
    recursive = F.db.Column(F.db.Boolean)
    vfs = F.db.Column(F.db.String)
    commands = F.db.Column(F.db.String)
    schedule_mode = F.db.Column(F.db.String)
    schedule_interval = F.db.Column(F.db.String)
    schedule_auto_start = F.db.Column(F.db.Boolean)
    status = F.db.Column(F.db.String)
    journal = F.db.Column(F.db.Text)

    def __init__(self, task: str, schedule_mode: str = FF_SCHEDULE_KEYS[0], schedule_auto_start: bool = False,
                 desc: str = None, target: str = None, recursive: bool = False,
                 vfs: str = None, commands: str = None):
        self.ctime = datetime.now()
        self.ftime = datetime(1970, 1, 1)
        self.task = task
        self.schedule_mode = schedule_mode
        self.schedule_auto_start = schedule_auto_start
        self.desc = desc
        self.target = target
        self.recursive = recursive
        self.vfs = vfs
        self.commands = commands
        self.status = STATUS_KEYS[0]

    @classmethod
    def make_query(cls, request: LocalProxy, order: str ='desc', search: str = '', option1: str = 'all', option2: str = 'all') -> Query:
        '''override'''
        with F.app.app_context():
            query = cls.make_query_search(F.db.session.query(cls), search, cls.target)
            if option1 != 'all':
                query = query.filter(cls.task == option1)
            if option2 != 'all':
                query = query.filter(cls.status == option2)
            if order == 'desc':
                query = query.order_by(desc(cls.id))
            else:
                query = query.order_by(cls.id)
            return query

    def set_status(self, status: str, save: bool = True) -> 'Job':
        if status in STATUS_KEYS:
            self.status = status
            if status == STATUS_KEYS[2]:
                self.ftime = datetime.now()
            if save:
                self.save()
        else:
            P.logger.error(f'wrong status: {status}')
        return self

    @classmethod
    def web_list(cls, req: LocalProxy) -> dict[str, Any] | None:
        '''override'''
        try:
            ret = {}
            page = 1
            page_size = 30
            search = ''
            if 'page' in req.form:
                page = int(req.form['page'])
            if 'keyword' in req.form:
                search = req.form['keyword'].strip()
            option1 = req.form.get('option1', 'all')
            option2 = req.form.get('option2', 'all')
            order = req.form['order'] if 'order' in req.form else 'desc'
            query = cls.make_query(req, order=order, search=search, option1=option1, option2=option2)
            count = query.count()
            query = query.limit(page_size).offset((page-1)*page_size)
            lists = query.all()
            ret['list'] = []
            for item in lists:
                item = item.as_dict()
                item['is_include'] = True if F.scheduler.is_include(cls.create_schedule_id(item['id'])) else False
                item['is_running'] = True if F.scheduler.is_running(cls.create_schedule_id(item['id'])) else False
                ret['list'].append(item)
            ret['paging'] = cls.get_paging_info(count, page, page_size)
            P.ModelSetting.set(f'{SCHEDULE}_last_list_option', f'{order}|{page}|{search}|{option1}|{option2}')
            return ret
        except Exception as e:
            P.logger.error(f"Exception:{str(e)}")
            P.logger.error(traceback.format_exc())

    @classmethod
    def create_schedule_id(cls, job_id: int) -> str:
        return f'{__package__}_{job_id}'
