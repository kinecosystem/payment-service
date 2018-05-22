import socket
import random
from . import config


IP = config.STATSD_HOST
PORT = config.STATSD_PORT


class Sample(object):
    """A sample for statsd.

    # to send a single count metric (+1):
    >>> Sample('event').count().send()

    # or aggregated metrics
    >>> Sample('event').time(102).count(4).send()

    # or with dimentions
    >>> Sample('user.register', country='israel', origin='facebook').time(120).add_set('user:123').send()
    """
    def __init__(self, event, **dimentions):
        self.message = event + ''.join(',%s=%s' % (k, v) for k, v in dimentions.items())

    def send(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(self.message.encode(), (IP, PORT))
        except (socket.error, RuntimeError):
            pass

    def add_set(self, item):
        self.message += ':%s|s' % item
        return self

    @classmethod
    def _should_skip(cls, sample_rate):
        if sample_rate and sample_rate < 1:
            if random.random() > sample_rate:
                return True
        return False

    def count(self, amount=1, sample_rate=None):
        if self._should_skip(sample_rate):
            return self

        self.message += ':%s|c' % amount
        if sample_rate:
            self.message += '|@%s' % sample_rate
        return self

    def time(self, time, sample_rate=None):
        if self._should_skip(sample_rate):
            return self

        self.message += ':%s|ms' % time
        if sample_rate:
            self.message += '|@%s' % sample_rate
        return self

    def histogram(self, value):
        self.message += ':%s|h' % value
        return self

    def guage(self, value):
        """value can be -x x or '+x'"""
        self.message += ':%s|g' % value
        return self
