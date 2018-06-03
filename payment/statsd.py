import types

from datadog import DogStatsd
from .config import STATSD_PORT, STATSD_HOST


statsd = DogStatsd(STATSD_HOST, STATSD_PORT, namespace='payment')


def inc_count(self, metric, value, tags):
    """both increment the metric by the given value and set a counter on it."""
    self.increment(metric, value, tags)
    self.increment('%s.count' % metric, tags)


statsd.inc_count = types.MethodType(inc_count, statsd)
