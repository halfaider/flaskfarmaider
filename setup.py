import pathlib
import time
import threading

from framework.init_main import Framework
from framework.scheduler import Job as FrameworkJob
from plugin.create_plugin import create_plugin_instance
from plugin.create_plugin import PluginBase
from plugin.logic_module_base import PluginModuleBase, PluginPageBase
from plugin.model_base import ModelBase
from plugin.route import default_route_socketio_module
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
        time.sleep(5)


threading.Thread(target=check_celery, daemon=True).start()

from .presenters import Setting
from .presenters import Schedule
from .presenters import Manual
from .presenters import Tool

PLUGIN.set_module_list([Setting, Schedule, Manual, Tool])