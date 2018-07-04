import kin
import os

class config:
    STELLAR_HORIZON_URL = 'https://horizon-testnet.stellar.org/'
    STELLAR_NETWORK = 'TESTNET'
    STELLAR_KIN_ISSUER_ADDRESS = 'GCKG5WGBIJP74UDNRIRDFGENNIH5Y3KBI5IHREFAJKV4MQXLELT7EX6V'
    STELLAR_BASE_SEED = os.environ['STELLAR_BASE_SEED']
    STELLAR_INITIAL_XLM_AMOUNT = 10
    DEBUG = True
    build = {'commit': 'XXX'}


kin_sdk = kin.SDK(
    secret_key=config.STELLAR_BASE_SEED,
    horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
    network=config.STELLAR_NETWORK)
# XXX testing


def print_me(address, data):
    try:
        print('='*100)
        print('got data1:', address, data)
        print('-'*100)
        print data.ledger, data.paging_token
        print('='*100)
        return data.ledger
    except Exception as e:
        print('failed', e)


def blah(address, cursor='now'):
    gen = kin_sdk.monitor_accounts_kin_payments_gen([address], cursor)  # XXX this starts a thread that I have no control over :(
    print('starting from %s' % cursor)
    for add, data in gen:
        print_me(add, data)


if __name__ == '__main__':
    import sys
    blah('GBOQY4LENMPZGBROR7PE5U3UXMK22OTUBCUISVEQ6XOQ2UDPLELIEC4J', sys.argv[1])
