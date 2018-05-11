import os
from datetime import datetime


STELLAR_HORIZON_URL = 'https://horizon-testnet.stellar.org/'
STELLAR_NETWORK = 'TESTNET'
STELLAR_KIN_ISSUER_ADDRESS = 'GCKG5WGBIJP74UDNRIRDFGENNIH5Y3KBI5IHREFAJKV4MQXLELT7EX6V'

STELLAR_CHANNEL_SEEDS = os.environ['STELLAR_CHANNEL_SEEDS'].split(',')
STELLAR_BASE_SEED = os.environ['STELLAR_BASE_SEED']
STELLAR_INITIAL_XLM_AMOUNT = 10

REDIS = os.environ['APP_REDIS']
APP_NAME = os.environ.get('APP_NAME', 'payment-service')

DEBUG = os.environ.get('APP_DEBUG', 'true').lower() == 'true'
build = {'commit': os.environ.get('BUILD_COMMIT'),
         'timestamp': os.environ.get('BUILD_TIMESTAMP'),
         'start_time': datetime.utcnow().isoformat()}
