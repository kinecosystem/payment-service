import os
from datetime import datetime


STELLAR_HORIZON_URL = os.environ['STELLAR_HORIZON_URL']
STELLAR_NETWORK = os.environ['STELLAR_NETWORK']
STELLAR_KIN_ISSUER_ADDRESS = os.environ['STELLAR_KIN_ISSUER_ADDRESS']
STELLAR_KIN_TOKEN_NAME = os.environ['STELLAR_KIN_TOKEN_NAME']

STELLAR_CHANNEL_SEEDS = os.environ['STELLAR_CHANNEL_SEEDS'].split(',')
STELLAR_BASE_SEED = os.environ['STELLAR_BASE_SEED']
STELLAR_INITIAL_XLM_AMOUNT = float(os.environ['STELLAR_INITIAL_XLM_AMOUNT'])

REDIS = os.environ['APP_REDIS']
APP_NAME = os.environ.get('APP_NAME', 'payment-service')

STATSD_HOST = os.environ.get('STATSD_HOST', 'localhost')
STATSD_PORT = int(os.environ.get('STATSD_PORT', 8125))

DEBUG = os.environ.get('APP_DEBUG', 'true').lower() == 'true'
build = {'commit': os.environ.get('BUILD_COMMIT'),
         'timestamp': os.environ.get('BUILD_TIMESTAMP'),
         'start_time': datetime.utcnow().isoformat()}
