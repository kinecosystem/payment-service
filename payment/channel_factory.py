from .blockchain import kin_sdk, init as init_sdk, create_wallet, get_wallet
from . import config
from hashlib import sha256
from kin.sdk import Keypair
from kin import AccountExistsError


INITIAL_XLM_AMOUNT = 5
MEMO_INIT = 'kin-init_channel'
MEMO_TOPUP = 'kin-topup-channel'


def generate_key(idx):
    """HD wallet - generate key based on root wallet + idx + salt."""
    idx_bytes = idx.to_bytes(2, 'big')
    root_seed = Keypair.from_seed(config.STELLAR_BASE_SEED).raw_seed()
    return Keypair.from_raw_seed(sha256(root_seed + idx_bytes + config.CHANNEL_SALT.encode()).digest()[:32])


def top_up(public_address, lower_limit=INITIAL_XLM_AMOUNT-1, upper_limit=INITIAL_XLM_AMOUNT):
    wallet = get_wallet(public_address)
    if wallet.native_balance < lower_limit:
        kin_sdk().send_native(public_address, upper_limit - wallet.native_balance, MEMO_TOPUP)


def get_next_channel_id():
    """get the next available channel_id from redis."""
    return 0


def init_sdk_with_channel():
    """gets next channel_id from redis, generates address/ tops up and inits sdk."""
    channel_id = get_next_channel_id()
    keys = generate_key(channel_id)
    public_address = keys.address().decode()
    private_seed = keys.seed().decode()
    try:
        init_sdk(config.STELLAR_BASE_SEED)
        create_wallet(public_address, MEMO_INIT, INITIAL_XLM_AMOUNT)
    except AccountExistsError:
        top_up(public_address)
    
    print ('# create channel: %s' % public_address)
    init_sdk(config.STELLAR_BASE_SEED, [private_seed])
