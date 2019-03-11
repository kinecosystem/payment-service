import contextlib
import time
from random import randint
from hashlib import sha256
from kin_base import Keypair
from .errors import NoAvailableChannel
from .utils import lock, safe_int
from . import config
from .statsd import statsd
from .redis_conn import redis_conn
from .blockchain import Blockchain
from .log import get as get_log
from kin import KinErrors


log = get_log()

INITIAL_XLM_AMOUNT = 3
DEFAULT_MAX_CHANNELS = config.MAX_CHANNELS
MAX_LOCK_TRIES = 100
SLEEP_BETWEEN_LOCKS = 0.01
MEMO_INIT = 'kin-init_channel'


def generate_key(root_wallet: Blockchain, idx):
    """HD wallet - generate key based on root wallet + idx + salt."""
    idx_bytes = idx.to_bytes(2, 'big')
    root_seed = root_wallet.write_sdk.raw_seed
    return Keypair.from_raw_seed(sha256(root_seed + idx_bytes + config.CHANNEL_SALT.encode()).digest()[:32])


@contextlib.contextmanager
def get_next_channel_id():
    """get the next available channel_id from redis."""
    max_channels = safe_int(redis_conn.get('MAX_CHANNELS'), DEFAULT_MAX_CHANNELS)
    for i in range(MAX_LOCK_TRIES):
        channel_id = randint(0, max_channels - 1)
        with lock(redis_conn, 'channel:{}'.format(channel_id), blocking_timeout=0) as locked_succeeded:
            if locked_succeeded:
                start_t = time.time()
                try:
                    redis_conn.sadd('channel_locks', channel_id)
                    statsd.gauge('channel_lock', redis_conn.scard('channel_locks'))
                    yield channel_id
                finally:
                    statsd.timing('channel_lock_time', time.time() - start_t)
                    redis_conn.srem('channel_locks', channel_id)
                    statsd.gauge('channel_lock', redis_conn.scard('channel_locks'))
                return  # end generator
        time.sleep(SLEEP_BETWEEN_LOCKS)
    raise NoAvailableChannel()


@contextlib.contextmanager
def get_channel(root_wallet: Blockchain):
    """gets next channel_id from redis and generates address (creating the wallet if needed)."""
    with get_next_channel_id() as channel_id:
        keys = generate_key(root_wallet, channel_id)
        public_address = keys.address().decode()
        try:
            root_wallet.create_wallet(public_address)  # XXX this causes a race-condition
            log.info('# created channel: %s: %s' % (channel_id, public_address))
        except KinErrors.AccountExistsError:
                log.info('# existing channel: %s: %s' % (channel_id, public_address))

        yield keys.seed().decode()
