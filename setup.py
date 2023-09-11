import pathlib
import time
import threading

from flask import Response, render_template, jsonify
from werkzeug.local import LocalProxy
from flask_sqlalchemy.query import Query
from sqlalchemy import desc, text
from plexapi.server import PlexServer
import flask_login

from framework.init_main import Framework
from framework.scheduler import Job as FrameworkJob
from plugin.create_plugin import create_plugin_instance
from plugin.create_plugin import PluginBase
from plugin.logic_module_base import PluginModuleBase, PluginPageBase
from plugin.model_base import ModelBase
from system.setup import P as system_plugin

from .constants import OPTS

PLUGIN = P = create_plugin_instance(OPTS)
LOGGER = PLUGIN.logger
CONFIG = PLUGIN.ModelSetting
FRAMEWORK = Framework.get_instance()
DEPEND_USER_YAML = pathlib.Path(f'{FRAMEWORK.config["path_data"]}/db/flaskfarmaider.yaml')
CELERY_INSPECT = FRAMEWORK.celery.control.inspect()
CELERY_ACTIVE = False

def check_celery():
    global CELERY_ACTIVE
    while True:
        CELERY_ACTIVE = True if CELERY_INSPECT.active() else False
        time.sleep(10)

threading.Thread(target=check_celery, daemon=True).start()

from .presenters import Setting
from .presenters import Schedule
from .presenters import Manual
from .presenters import Tool

PLUGIN.set_module_list([Setting, Schedule, Manual, Tool])