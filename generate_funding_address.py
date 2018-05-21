import time
import os
from functools import wraps
import kin
import requests
from kin.sdk import Keypair
import stellar_base


class config:
    KIN_FAUCET = os.getenv('KIN_FAUCET', 'http://159.65.84.173:5005')
    XLM_FAUCET = os.getenv('XLM_FAUCET', 'https://friendbot.stellar.org')
    STELLAR_HORIZON_URL = os.environ['STELLAR_HORIZON_URL']
    STELLAR_NETWORK = os.environ['STELLAR_NETWORK']
    STELLAR_KIN_ISSUER_ADDRESS = os.environ['STELLAR_KIN_ISSUER_ADDRESS']
    STELLAR_KIN_TOKEN_NAME = os.environ['STELLAR_KIN_TOKEN_NAME']
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


def _get_network_name():
    """hack: monkeypatch stellar_base to support private network."""
    if config.STELLAR_NETWORK in ['PUBLIC', 'TESTNET']:
        return config.STELLAR_NETWORK
    else:
        PRIVATE = 'PRIVATE'
        # register the private network with the given passphrase
        stellar_base.network.NETWORKS[PRIVATE] = config.STELLAR_NETWORK
        return PRIVATE


@retry(5, 1)
def trust_kin(private_seed):
    kin_sdk = kin.SDK(
        secret_key=private_seed,
        horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
        network=_get_network_name(),
        kin_asset=kin.Asset.native())
    kin_asset = stellar_base.asset.Asset(config.STELLAR_KIN_TOKEN_NAME, config.STELLAR_KIN_ISSUER_ADDRESS)
    kin_sdk._trust_asset(kin_asset)


@retry(5, 1)
def fund_lumens(public_address):
    res = requests.get(config.XLM_FAUCET,
                       params={'addr': public_address})
    res.raise_for_status()
    return res.json()


@retry(5, 3)
def fund_kin(public_address):
    res = requests.get(config.KIN_FAUCET + '/fund',
                       params={'account': public_address,
                               'amount': config.AMOUNT})
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

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(config.OUTPUT_DIR, '.secrets'), 'w') as f:
        print('export STELLAR_BASE_SEED=%s' % private_seed, file=f)
        print('export STELLAR_CHANNEL_SEEDS=%s' % private_seed, file=f)
        print('export STELLAR_ADDRESS=%s' % public_address, file=f)
