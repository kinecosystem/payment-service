  #!/usr/bin/env python
import sys
from rq import Connection, Worker, Queue
from rq.job import Job, JobStatus

# Preload libraries
from payment.statsd import statsd
from payment.log import get as get_log
from payment import config
from payment.redis_conn import redis_conn


log = get_log()
q = Queue(connection=redis_conn)


def rq_error_handler(job: Job, exc_type, exc_value, traceback):
    statsd.increment('worker_error', tags=['job:%s' % job.func_name, 'error_type:%s' % exc_type, 'error:%s' % exc_value])
    log.error('worker error in job', func_name=job.func_name, args=job.args, exc_info=(exc_type, exc_value, traceback))

    # reset job state and retry the job
    job.set_status(JobStatus.QUEUED)
    job.exc_info = None
    q.enqueue_job(job)


with Connection():
    queue_names = ['default']
    w = Worker(queue_names, connection=redis_conn, exception_handlers=[rq_error_handler])
    w.work()
