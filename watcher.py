from payment.log import init as init_log
log = init_log()

from payment import watcher

watcher.worker(None)
