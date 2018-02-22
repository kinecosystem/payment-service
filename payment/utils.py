import contextlib


@contextlib.contextmanager
def lock(key):
    # try to lock
    yield
    # release lock
