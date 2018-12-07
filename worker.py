  #!/usr/bin/env python
import sys
from rq import Connection, Worker, Queue
from rq.job import Job, JobStatus

# Preload libraries
from payment.statsd import statsd
from payment.log import get as get_log
from payment import config
from payment.errors import PersitentError
from payment.redis_conn import redis_conn


log = get_log()


def rq_error_handler(job: Job, exc_type, exc_value, traceback):
    statsd.increment('worker_error', tags=['job:%s' % job.func_name, 'error_type:%s' % exc_type, 'error:%s' % exc_value])
    log.error('worker error in job', func_name=job.func_name, args=job.args, exc_info=(exc_type, exc_value, traceback))

    # reset job state and retry the job
    if exc_type != PersitentError:
        job.set_status(JobStatus.QUEUED)
        job.exc_info = None
        q = Queue('low', connection=redis_conn)
        q.enqueue_job(job)
    else:
        statsd.increment('worker_persistent_error', tags=['job:%s' % job.func_name, 'error_type:%s' % exc_type, 'error:%s' % exc_value])
        log.error('not retriying PersitentError', e=exc_value)


if __name__ == '__main__':
    with Connection():
        queue_names = ['high', 'medium', 'low', 'default']
        w = Worker(queue_names, connection=redis_conn, exception_handlers=[rq_error_handler])
        w.work()
