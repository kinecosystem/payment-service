from datadog import DogStatsd
from .config import STATSD_PORT, STATSD_HOST

statsd = DogStatsd(STATSD_HOST, STATSD_PORT, namespace='payment')
