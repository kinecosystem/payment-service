import time
import os
from functools import wraps
import kin
import requests
from kin.sdk import Keypair
from payment.utils import retry, get_network_name
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


def wrap_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise Exception('%s failed: %s' % (func.__name__, e))
    return wrapper


@wrap_error
@retry(5, 1)
def trust_kin(private_seed):
    kin_sdk = kin.SDK(
        secret_key=private_seed,
        horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
        network=get_network_name(config.STELLAR_NETWORK),
        kin_asset=kin.Asset.native())
    kin_asset = stellar_base.asset.Asset(config.STELLAR_KIN_TOKEN_NAME, config.STELLAR_KIN_ISSUER_ADDRESS)
    kin_sdk._trust_asset(kin_asset)


@wrap_error
@retry(5, 1)
def fund_lumens(public_address):
    res = requests.get(config.XLM_FAUCET,
                       params={'addr': public_address})
    res.raise_for_status()
    return res.json()


@wrap_error
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

    print('# creating %s' % public_address)
    fund_lumens(public_address)
    trust_kin(private_seed)
    fund_kin(public_address)

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(config.OUTPUT_DIR, '.secrets'), 'w') as f:
        print('export STELLAR_BASE_SEED=%s' % private_seed, file=f)
