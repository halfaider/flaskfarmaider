TASK_KEYS = ('refresh_scan', 'refresh', 'scan', 'pm_ready_refresh', 'clear', 'startup', 'forget')
TASKS = {
    TASK_KEYS[0]: {'key': TASK_KEYS[0], 'name': '새로고침 후 스캔', 'desc': 'Rclone 리모트 콘트롤 서버에 vfs/refresh 요청 후 플렉스 스캔', 'enable': False},
    TASK_KEYS[1]: {'key': TASK_KEYS[1], 'name': '새로고침', 'desc': 'Rclone 리모트 콘트롤 서버에 vfs/refresh 요청', 'enable': False},
    TASK_KEYS[2]: {'key': TASK_KEYS[2], 'name': '스캔', 'desc': '플렉스 스캔을 요청', 'enable': False},
    TASK_KEYS[3]: {'key': TASK_KEYS[3], 'name': 'Plexmate Ready 새로고침', 'desc': 'Plexmate의 READY 상태인 항목들을 Rclone 리모트 서버에 vfs/refresh 요청', 'enable': False},
    TASK_KEYS[4]: {'key': TASK_KEYS[4], 'name': 'Plexmate 파일 정리', 'desc': 'Plexmate의 라이브러리 파일 정리를 일정으로 등록', 'enable': False},
    TASK_KEYS[5]: {'key': TASK_KEYS[5], 'name': '스타트업', 'desc': 'Flaskfarm 시작시 필요한 OS 명령어를 실행', 'enable': False},
    TASK_KEYS[6]: {'key': TASK_KEYS[6], 'name': '경로 캐시 삭제', 'desc': 'Rclone 리모트 콘트롤 서버에 vfs/forget 요청', 'enable': False},
}

TOOL_TRASH_KEYS = ('trash_refresh', 'trash_scan', 'trash_empty', 'trash_refresh_scan', 'trash_refresh_scan_empty')
TOOL_TRASHES = {
    TOOL_TRASH_KEYS[0]: {'key': TOOL_TRASH_KEYS[0], 'name': '새로고침', 'desc': None},
    TOOL_TRASH_KEYS[1]: {'key': TOOL_TRASH_KEYS[1], 'name': '스캔', 'desc': None},
    TOOL_TRASH_KEYS[2]: {'key': TOOL_TRASH_KEYS[2], 'name': '비우기', 'desc': None},
    TOOL_TRASH_KEYS[3]: {'key': TOOL_TRASH_KEYS[3], 'name': '새로고침 > 스캔', 'desc': None},
    TOOL_TRASH_KEYS[4]: {'key': TOOL_TRASH_KEYS[4], 'name': '새로고침 > 스캔 > 비우기', 'desc': None},
}

STATUS_KEYS = ('ready', 'running', 'finish', 'stopping')
STATUSES = {
    STATUS_KEYS[0]: {'key': STATUS_KEYS[0], 'name': '대기', 'desc': None},
    STATUS_KEYS[1]: {'key': STATUS_KEYS[1], 'name': '실행', 'desc': None},
    STATUS_KEYS[2]: {'key': STATUS_KEYS[2], 'name': '완료', 'desc': None},
    STATUS_KEYS[3]: {'key': STATUS_KEYS[3], 'name': '중지', 'desc': None},
}

FF_SCHEDULE_KEYS = ('none', 'startup', 'schedule')
FF_SCHEDULES = {
    FF_SCHEDULE_KEYS[0]: {'key': FF_SCHEDULE_KEYS[0], 'name': '없음', 'desc': None},
    FF_SCHEDULE_KEYS[1]: {'key': FF_SCHEDULE_KEYS[1], 'name': '시작시 실행', 'desc': None},
    FF_SCHEDULE_KEYS[2]: {'key': FF_SCHEDULE_KEYS[2], 'name': '시간 간격', 'desc': None},
}

SCAN_MODE_KEYS = ('web', 'plexmate')
SCAN_MODES = {
    SCAN_MODE_KEYS[0]: {'key': SCAN_MODE_KEYS[0], 'name': 'Plex Web API', 'desc': None},
    SCAN_MODE_KEYS[1]: {'key': SCAN_MODE_KEYS[1], 'name': 'Plexmate 스캔', 'desc': None},
}

SECTION_TYPE_KEYS = ('movie', 'show', 'artist', 'photo')
SECTION_TYPES = {
    SECTION_TYPE_KEYS[0]: {'key': SECTION_TYPE_KEYS[0], 'name': '영화', 'desc': None},
    SECTION_TYPE_KEYS[1]: {'key': SECTION_TYPE_KEYS[1], 'name': 'TV', 'desc': None},
    SECTION_TYPE_KEYS[2]: {'key': SECTION_TYPE_KEYS[2], 'name': '음악', 'desc': None},
    SECTION_TYPE_KEYS[3]: {'key': SECTION_TYPE_KEYS[3], 'name': '사진', 'desc': None},
}

SEARCH_KEYS= ('task', 'desc', 'target', 'status', 'schedule_interval')
SEARCHES = {
    SEARCH_KEYS[0]: {'key': SEARCH_KEYS[0], 'name': '작업', 'desc': None},
    SEARCH_KEYS[1]: {'key': SEARCH_KEYS[1], 'name': '설명', 'desc': None},
    SEARCH_KEYS[2]: {'key': SEARCH_KEYS[2], 'name': '로컬 경로', 'desc': None},
    SEARCH_KEYS[3]: {'key': SEARCH_KEYS[3], 'name': '상태', 'desc': None},
    SEARCH_KEYS[4]: {'key': SEARCH_KEYS[4], 'name': '시간 간격', 'desc': None},
}

PLEX_MEDIA_TYPE_VALUES = {
    1: 'movie',
    2: 'show',
    3: 'season',
    4: 'episode',
    5: 'trailer',
    6: 'comic',
    7: 'person',
    8: 'artist',
    9: 'album',
    10: 'track',
    11: 'picture',
    12: 'clip',
    13: 'photo',
    14: 'photoalbum',
    15: 'playlist',
    16: 'playlistFolder',
    18: 'collection',
    42: 'optimizedVersion'
}

OPTS = {
    'use_db': True,
    'use_default_setting': True,
    'home_module': 'schedule',
    'menu': {
        'uri': __package__,
        'name': __package__.upper(),
        'list': [
            {
                'uri': 'setting',
                'name': '설정',
            },
            {
                'uri': 'schedule',
                'name': '일정',
            },
            {
                'uri': 'tool',
                'name': '도구',
                'list': [
                    {'uri': 'trash', 'name': 'Plex 휴지통 스캔'},
                    {'uri': 'oauth', 'name': 'Google OAuth'},
                ]
            },
            {
                'uri': 'manual',
                'name': '도움말',
            },
            {
                'uri': 'log',
                'name': '로그',
            },
        ]
    },
    'setting_menu': None,
    'default_route': 'normal',
}