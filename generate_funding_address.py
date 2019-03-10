import os
import requests
from kin import Keypair
from payment.utils import retry


class config:
    KIN_FAUCET = os.getenv('KIN_FRIENDBOT')
    STELLAR_HORIZON_URL = os.environ['STELLAR_HORIZON_URL']
    STELLAR_NETWORK = os.environ['STELLAR_NETWORK']
    OUTPUT_DIR = os.getenv('OUTPUT_DIR', '.')
    AMOUNT = 100000
    REQ_TIMEOUT = 10


def wrap_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise Exception('%s failed: %s' % (func.__name__, e))
    return wrapper


@wrap_error
@retry(5, 1)
def fund_kin(public_address):
    res = requests.get(config.KIN_FAUCET,
                       params={'addr': public_address},
                       timeout=config.REQ_TIMEOUT)
    res.raise_for_status()
    return res.json()


def generate():
    # generates a file that can be 'sourced' and creates environment vars for
    # payment-service
    keys = Keypair()
    public_address = keys.public_address()
    private_seed = keys.secret_seed()

    print('# creating %s' % public_address)
    fund_kin(public_address)
    return public_address, private_seed


if __name__ == '__main__':
    public_address, private_seed = generate()
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(config.OUTPUT_DIR, '.secrets'), 'w') as f:
        print('export STELLAR_BASE_SEED=%s' % private_seed, file=f)
        print('export STELLAR_ADDRESS=%s' % public_address, file=f)
