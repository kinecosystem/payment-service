import contextlib
import time
from random import randint
from hashlib import sha256
from kin.sdk import Keypair
from kin import AccountExistsError
from .errors import NoAvailableChannel
from .utils import lock, safe_int
from . import config
from .statsd import statsd
from .redis_conn import redis_conn
from .blockchain import Blockchain
from .log import get as get_log


log = get_log()

INITIAL_XLM_AMOUNT = 3
DEFAULT_MAX_CHANNELS = config.MAX_CHANNELS
MAX_LOCK_TRIES = 100
SLEEP_BETWEEN_LOCKS = 0.01
MEMO_INIT = 'kin-init_channel'
MEMO_TOPUP = 'kin-topup-channel'


def generate_key(root_wallet: Blockchain, idx):
    """HD wallet - generate key based on root wallet + idx + salt."""
    idx_bytes = idx.to_bytes(2, 'big')
    root_seed = root_wallet.write_sdk.base_keypair.raw_seed()
    return Keypair.from_raw_seed(sha256(root_seed + idx_bytes + config.CHANNEL_SALT.encode()).digest()[:32])


def top_up(root_wallet: Blockchain, public_address, lower_limit=INITIAL_XLM_AMOUNT-1, upper_limit=INITIAL_XLM_AMOUNT):
    wallet = Blockchain.get_wallet(public_address)
    if wallet.native_balance < lower_limit:
        root_wallet.send_native(public_address, upper_limit - wallet.native_balance, MEMO_TOPUP)
        return True
    return False


@contextlib.contextmanager
def get_next_channel_id():
    """get the next available channel_id from redis."""
    max_channels = safe_int(redis_conn.get('MAX_CHANNELS'), DEFAULT_MAX_CHANNELS)
    for i in range(MAX_LOCK_TRIES):
        channel_id = randint(0, max_channels - 1)
        with lock(redis_conn, 'channel:{}'.format(channel_id), blocking_timeout=0) as is_locked:
            if is_locked:
                try:
                    statsd.increment('channel_lock')
                    start_t = time.time()
                    yield channel_id
                finally:
                    statsd.decrement('channel_lock')
                    statsd.timing('channel_lock_time', time.time() - start_t)
                return  # end generator
        time.sleep(SLEEP_BETWEEN_LOCKS)
    raise NoAvailableChannel()


@contextlib.contextmanager
def get_channel(root_wallet: Blockchain):
    """gets next channel_id from redis, generates address/ tops up and inits sdk."""
    with get_next_channel_id() as channel_id:
        keys = generate_key(root_wallet, channel_id)
        public_address = keys.address().decode()
        try:
            root_wallet.create_wallet(public_address, MEMO_INIT, INITIAL_XLM_AMOUNT)  # XXX this causes a race-condition
            log.info('# created channel: %s: %s' % (channel_id, public_address))
        except AccountExistsError:
            if top_up(root_wallet, public_address):
                log.info('# top up channel: %s: %s' % (channel_id, public_address))
            else:
                log.info('# existing channel: %s: %s' % (channel_id, public_address))

        yield keys.seed().decode()
