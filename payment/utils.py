import contextlib
import time
from functools import wraps


@contextlib.contextmanager
def lock(redis_conn, key):
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
                    print('# retry %s: %s' % (func.__name__, i))
                    if i == times - 1:
                        raise
                    else:
                        time.sleep(delay)
        return wrapper
    return decorator


def get_network_name(stellar_network):
    """hack: monkeypatch stellar_base to support private network."""
    if stellar_network in ['PUBLIC', 'TESTNET']:
        return stellar_network
    else:
        import stellar_base
        PRIVATE = 'PRIVATE'
        # register the private network with the given passphrase
        stellar_base.network.NETWORKS[PRIVATE] = stellar_network
        return PRIVATE
