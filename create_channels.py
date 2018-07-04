import os
import sys
from payment.blockchain import kin_sdk
from payment import config
from hashlib import sha256
from kin.sdk import Keypair
from kin import AccountExistsError


INITIAL_XLM_AMOUNT = 5
NUM_CHANNELS = 4
HD_SALT = os.environ['APP_HD_SALT'].encode()


def _generate_key(idx):
    return Keypair.random()


def generate_key(idx):
    """HD wallet - generate key based on root wallet + idx + salt."""
    idx_bytes = idx.to_bytes(2, 'big')
    root_seed = Keypair.from_seed(config.STELLAR_BASE_SEED).raw_seed()
    return Keypair.from_raw_seed(sha256(root_seed + idx_bytes + HD_SALT).digest()[:32])


def create_wallet(public_address):
    try:
        account_exists = kin_sdk().check_account_exists(public_address)
    except Exception:
        pass
    else:
        if account_exists:
            return

    memo = '1-kin-init_channel'
    try:
        tx_id = kin_sdk().create_account(public_address, INITIAL_XLM_AMOUNT, memo)
        return tx_id
    except AccountExistsError:
        return
    # all other errors will crash this


if __name__ == '__main__':
    start = int(sys.argv[1]) # starting channel
    for idx in range(start, start + NUM_CHANNELS):
        keys = generate_key(idx)
        public_address = keys.address().decode()
        private_seed = keys.seed().decode()

        create_wallet(public_address)
        
        print('#', idx, public_address)
        print(private_seed)
