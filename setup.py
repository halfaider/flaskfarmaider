from framework.init_main import Framework
from framework.scheduler import Job as FrameworkJob
from plugin.create_plugin import create_plugin_instance
from plugin.create_plugin import PluginBase
from plugin.logic_module_base import PluginModuleBase, PluginPageBase
from plugin.model_base import ModelBase
from plugin.route import default_route_socketio_module, default_route_socketio_page
from system.setup import P as system_plugin

from .constants import OPTS

PLUGIN = P = create_plugin_instance(OPTS)
LOGGER = PLUGIN.logger
CONFIG = PLUGIN.ModelSetting
FRAMEWORK = Framework.get_instance()

from .presenters import Setting
from .presenters import Schedule
from .presenters import Manual
from .presenters import Tool

PLUGIN.set_module_list([Setting, Schedule, Manual, Tool])
