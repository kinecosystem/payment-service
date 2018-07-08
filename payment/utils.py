import contextlib
import time
from functools import wraps
import redis
import logging


@contextlib.contextmanager
def lock(redis_conn, key, blocking_timeout=None):
    _lock = redis_conn.lock('__lock:{}'.format(key), blocking_timeout=blocking_timeout)
    is_locked = _lock.acquire()
    yield is_locked
    try:
        if is_locked:
            _lock.release()
            logging.warn("released %s" % key)
        else:
            logging.warn("did not release %s" % key)
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


def get_network_name(network_name):
    """hack: monkeypatch stellar_base to support private network."""
    import stellar_base
    if network_name in stellar_base.network.NETWORKS:
        return network_name
    else:  # network_name is actually a passphrase
        PRIVATE = 'PRIVATE'
        # register the private network with the given passphrase
        stellar_base.network.NETWORKS[PRIVATE] = network_name
        return PRIVATE


def get_network_passphrase(network_name):
    import stellar_base
    if network_name not in stellar_base.network.NETWORKS:
        return network_name 
    return stellar_base.network.NETWORKS[network_name]
