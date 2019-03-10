import contextlib
import time
from functools import wraps
import redis
import logging


@contextlib.contextmanager
def lock(redis_conn, key, blocking_timeout=None):
    _lock = redis_conn.lock('__lock:{}'.format(key), blocking_timeout=blocking_timeout, timeout=120)
    is_locked = _lock.acquire()
    try:
        yield is_locked
    finally:
        try:
            if is_locked:
                _lock.release()
        except redis.exceptions.LockError:
            logging.error("failed to release lock %s" % key)


def retry(times, delay=0.3, ignore=[]):
    """retry on errors that aren't ignored."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(times):
                try:
                    return func(*args, **kwargs)
                except tuple(ignore):  # ignored errors aren't retried
                    raise
                except Exception:
                    print('# retry %s: %s' % (func.__name__, i))
                    if i == times - 1:
                        raise
                    else:
                        time.sleep(delay)
        return wrapper
    return decorator


def safe_int(string, default):
    try:
        return int(string)
    except Exception:
        return default
