"""Log handling.

The logger is wrapped by a structured logger for easier parsing.
"""
import logging
import sys
from structlog import wrap_logger, configure
from structlog._frames import _find_first_app_frame_and_name
from structlog.processors import (TimeStamper, JSONRenderer, StackInfoRenderer,
                                  format_exc_info)
from structlog.stdlib import (add_log_level, filter_by_level, LoggerFactory,
                              BoundLogger)
from structlog.threadlocal import wrap_dict

from . import config


LOG_LEVEL_PROD = logging.INFO
LOG_LEVEL_DEBUG = logging.DEBUG


def add_app_context(logger, method_name, event_dict):
    """Add file, line, and function of log print."""
    f, name = _find_first_app_frame_and_name(['logging', __name__])
    event_dict['trace'] = {'file': f.f_code.co_filename,
                           'line': f.f_lineno,
                           'build': {'commit': config.build['commit']},
                           'function': f.f_code.co_name}
    return event_dict


def split_pos_args(logger, method_name, event_dict):
    """Change positional_args into a list of arg1,arg2..argn."""
    for i, arg in enumerate(event_dict.pop('positional_args', [])):
        event_dict['arg_%s' % (i + 1)] = arg
    return event_dict


def init():
    logging.basicConfig(stream=sys.stdout, format='%(message)s')

    logging.getLogger().setLevel(LOG_LEVEL_DEBUG if config.DEBUG
                                 else LOG_LEVEL_PROD)

    configure(
        processors=[
            filter_by_level,
            add_log_level,
            add_app_context,
            split_pos_args,
            TimeStamper(fmt='iso', utc=True),
            StackInfoRenderer(),
            format_exc_info,
            JSONRenderer(sort_keys=True)
        ],
        context_class=wrap_dict(dict),
        logger_factory=LoggerFactory(),
        wrapper_class=BoundLogger,
        cache_logger_on_first_use=True,
    )

    for logger_name in ['requests', 'statsd', 'amqpstorm', 'datadog.dogstatsd']:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    return get()


def get(name=__name__):
    """Return a structlog."""
    return wrap_logger(logging.getLogger(name)).bind()
