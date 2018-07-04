import time
from functools import wraps


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
