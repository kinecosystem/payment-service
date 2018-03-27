import contextlib
import time
from functools import wraps
from .redis_conn import redis_conn


@contextlib.contextmanager
def lock(key):
    _lock = redis_conn.lock('__lock:{}'.format(key), blocking_timeout=10)
    _lock.acquire()
    yield
    _lock.release()


def retry(times, delay=0.3):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if i == times - 1:
                        raise
                    else:
                        time.sleep(delay)
        return wrapper
    return decorator
