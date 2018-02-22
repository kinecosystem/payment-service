import time
from functools import wraps
from logging import getLogger
from flask import request, jsonify

logger = getLogger()


class BaseError(Exception):
    http_code = 400
    code = 4000

    def __init__(self, message):
        self.message = message

    def to_dict(self):
        return {'code': self.code, 'error': self.message}


def handle_errors(f):
    """Decorate a function to log exceptions it throws."""
    @wraps(f)
    def inner(*args, **kwargs):
        try:
            start_time = time.time()
            return f(*args, **kwargs)
        except Exception as e:
            if not isinstance(e, BaseError):
                e = BaseError(str(e))
            logger.exception('uncaught error {}, {}, {}'.format(e, e.to_dict(), e.message))
            return jsonify(e.to_dict()), e.http_code
        finally:
            logger.info('path {} took {}'.format(request.path, time.time() - start_time))

    return inner
