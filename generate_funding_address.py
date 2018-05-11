import time
import os
from functools import wraps
import kin
import requests
from kin.sdk import Keypair


KIN_FAUCET = os.getenv('KIN_FAUCET', 'http://159.65.84.173:5005')
XLM_FAUCET = os.getenv('XLM_FAUCET', 'https://friendbot.stellar.org')
OUTPUT_DIR = os.getenv('OUTPUT_DIR', '.')
AMOUNT = 100000


def retry(times, delay=0.3):
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
                        time.sleep(delay)
        return wrapper
    return decorator


@retry(5)
def trust_kin(private_seed):
    sdk = kin.SDK(network='TESTNET',
                  secret_key=private_seed,
                  kin_asset=kin.Asset.native())
    sdk._trust_asset(kin.KIN_ASSET_TEST)


@retry(5, 1)
def fund_lumens(public_address):
    res = requests.get(XLM_FAUCET,
                       params={'addr': public_address})
    res.raise_for_status()
    return res.json()


@retry(5, 3)
def fund_kin(public_address):
    res = requests.get(KIN_FAUCET + '/fund',
                       params={'account': public_address,
                               'amount': AMOUNT})
    res.raise_for_status()
    return res.json()


if __name__ == '__main__':
    # generates a file that can be 'sourced' and creates environment vars for
    # payment-service
    keys = Keypair.random()
    public_address = keys.address().decode()
    private_seed = keys.seed().decode()

    fund_lumens(public_address)
    trust_kin(private_seed)
    fund_kin(public_address)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, '.secrets'), 'w') as f:
        print('export STELLAR_BASE_SEED=%s' % private_seed, file=f)
        print('export STELLAR_CHANNEL_SEEDS=%s' % private_seed, file=f)
        print('export STELLAR_ADDRESS=%s' % public_address, file=f)
