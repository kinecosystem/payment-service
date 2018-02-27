import contextlib
import time
from functools import wraps
from threading import Lock


_lock = Lock()


@contextlib.contextmanager
def lock(key):
    _lock.acquire()
    yield
    _lock.release()


def retry(times):
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
                        time.sleep(0.1)
        return wrapper
    return decorator
