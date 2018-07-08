import contextlib
from hashlib import sha256
from kin.sdk import Keypair
from kin import AccountExistsError
from . import config
from .redis_conn import redis_conn
from .blockchain import Blockchain


INITIAL_XLM_AMOUNT = 5
DEFAULT_MAX_CHANNELS = 20
MEMO_INIT = 'kin-init_channel'
MEMO_TOPUP = 'kin-topup-channel'


def generate_key(idx):
    """HD wallet - generate key based on root wallet + idx + salt."""
    idx_bytes = idx.to_bytes(2, 'big')
    root_seed = Keypair.from_seed(config.STELLAR_BASE_SEED).raw_seed()
    return Keypair.from_raw_seed(sha256(root_seed + idx_bytes + config.CHANNEL_SALT.encode()).digest()[:32])


def top_up(root_wallet: Blockchain, public_address, lower_limit=INITIAL_XLM_AMOUNT-1, upper_limit=INITIAL_XLM_AMOUNT):
    wallet = Blockchain.get_wallet(public_address)
    if wallet.native_balance < lower_limit:
        root_wallet.send_native(public_address, upper_limit - wallet.native_balance, MEMO_TOPUP)


@contextlib.contextmanager
def get_next_channel_id():
    """get the next available channel_id from redis."""
    max_channels = redis_conn.get('MAX_CHANNELS') or DEFAULT_MAX_CHANNELS
    for channel_id in range(max_channels):
        with redis_conn.lock('lock:channel:%s' % channel_id, blocking_timeout=0) as is_locked:
            if not is_locked:
                continue
            yield channel_id
            break


@contextlib.contextmanager
def get_channel(root_wallet: Blockchain):
    """gets next channel_id from redis, generates address/ tops up and inits sdk."""
    with get_next_channel_id() as channel_id:
        keys = generate_key(channel_id)
        public_address = keys.address().decode()
        try:
            root_wallet.create_wallet(public_address, MEMO_INIT, INITIAL_XLM_AMOUNT)
            print('# created channel: %s' % public_address)
        except AccountExistsError:
            top_up(root_wallet, public_address)
            print('# top up channel: %s' % public_address)

        yield keys.seed().decode()
