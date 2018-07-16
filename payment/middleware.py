import time
from functools import wraps
from flask import request, jsonify
from .errors import BaseError
from .log import get as get_log
from .statsd import statsd


log = get_log()


def handle_errors(f):
    """Decorate a function to log exceptions it throws."""
    @wraps(f)
    def inner(*args, **kwargs):
        start_time = time.time()
        try:
            return f(*args, **kwargs)
        except Exception as e:
            if not isinstance(e, BaseError):
                e = BaseError(str(e))
            log.exception('uncaught error', error=e, payload=e.to_dict(), message=e.message)
            statsd.increment('server_error', tags=['path:%s' % request.url_rule.rule, 'error:%s' % e.message])
            return jsonify(e.to_dict()), e.http_code
        finally:
            log.info('response time', path=request.path, time=time.time() - start_time)
            statsd.timing('request', time.time() - start_time, tags=['path:%s' % request.url_rule.rule])

    return inner
