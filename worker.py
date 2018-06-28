#!/usr/bin/env python
import sys
from rq import Connection, Worker
from rq.job import Job

# Preload libraries
from payment.blockchain import kin_sdk
from payment.statsd import statsd
from payment.log import get as get_log
from payment.redis_conn import redis_conn


log = get_log()


def rq_error_handler(job: Job, exc_type, exc_value, traceback):
    statsd.increment('worker_error', tags=['job:%s' % job.func_name, 'error_type:%s' % exc_type, 'error:%s' % exc_value])
    log.error('worker error in job', func_name=job.func_name, args=job.args, exc_info=(exc_type, exc_value, traceback))


with Connection():
    qs = sys.argv[1:] or ['default']

    w = Worker(qs, connection=redis_conn, exception_handlers=[rq_error_handler])
    w.work()
