import traceback
import logging
from typing import Optional, Iterable

from watchdog.utils import load_class
from watchdog.events import (
    FileSystemEvent,
    RegexMatchingEventHandler,
    EVENT_TYPE_MOVED,
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MODIFIED,
    EVENT_TYPE_CLOSED,
    EVENT_TYPE_OPENED
)


logger = logging.getLogger(__name__)
EVENTS = [
    EVENT_TYPE_MOVED,
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MODIFIED,
    EVENT_TYPE_CLOSED,
    EVENT_TYPE_OPENED
]



class FlaskfarmHandler(RegexMatchingEventHandler):

    conduits = []

    def __init__(self,
                 regexes: Optional[Iterable[str]] = None,
                 ignore_regexes: Optional[Iterable[str]] = None,
                 ignore_directories: Optional[bool] = False,
                 case_sensitive: Optional[bool] = False,
                 conduits: Optional[Iterable[dict]] = None) -> None:
        super(FlaskfarmHandler, self).__init__(regexes, ignore_regexes, ignore_directories, case_sensitive)
        if conduits:
            for conduit in conduits:
                try:
                    name = conduit.pop('name')
                    _class = conduit.pop('class')
                except KeyError as ke:
                    logger.error(f'{ke} not in {conduit}')
                    continue
                events = conduit.pop('events', EVENTS)
                if not events:
                    events = EVENTS
                else:
                    unknown_events = []
                    for event in events:
                        if event not in EVENTS:
                            unknown_events.append(event)
                    if unknown_events:
                        logger.error(f'{unknown_events} not in {EVENTS}')
                        continue
                priority = int(conduit.pop('priority', 0))
                try:
                    conduit_cls = load_class(_class)
                    conduit_ins = conduit_cls(name, events, priority, **conduit)
                    self.conduits.append(conduit_ins)
                except Exception as e:
                    logger.error(f'{e}')
                    continue
            self.conduits.sort(key=lambda x : x.priority, reverse=True)

    def on_any_event(self, event: FileSystemEvent) -> None:
        event_dict = {
            'event_type': event.event_type,
            'is_directory': event.is_directory,
            'src_path': event.src_path,
            'dest_path': event.dest_path,
            'is_synthetic': event.is_synthetic
        }
        for conduit in self.conduits:
            if event_dict['event_type'] not in conduit.events:
                continue
            try:
                conduit.flow(event_dict)
            except Exception:
                logger.error(traceback.format_exc())
                continue
