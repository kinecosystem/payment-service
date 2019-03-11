  #!/usr/bin/env python
import sys
from uuid import uuid4
from rq import Connection, Worker
from rq.job import Job, JobStatus

# Preload libraries
from payment.statsd import statsd
from payment.log import get as get_log
from payment.errors import PersitentError
from payment.redis_conn import redis_conn
from payment.queue import q


log = get_log()


def rq_error_handler(job: Job, exc_type, exc_value, traceback):
    statsd.increment('worker_error', tags=['job:%s' % job.func_name, 'error_type:%s' % exc_type, 'error:%s' % exc_value])
    log.error('worker error in job', func_name=job.func_name, args=job.args, exc_info=(exc_type, exc_value, traceback))

    # reset job state and retry the job
    if exc_type != PersitentError:
        job.set_status(JobStatus.QUEUED)
        job.exc_info = None
        q.enqueue_job(job)
    else:
        statsd.increment('worker_persistent_error', tags=['job:%s' % job.func_name, 'error_type:%s' % exc_type, 'error:%s' % exc_value])
        log.error('not retriying PersitentError', e=exc_value)


if __name__ == '__main__':
    with Connection():
        queue_names = [q.name]
        worker_name = str(uuid4())
        w = Worker(queue_names, name=worker_name, connection=redis_conn, exception_handlers=[rq_error_handler])
        w.work()
