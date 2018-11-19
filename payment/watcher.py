import threading
import time

from .blockchain import Blockchain
from .queue import enqueue_payment_callback
from .log import get as get_log
from .models import Watcher, CursorManager
from .transaction_flow import TransactionFlow
from .utils import retry
from .statsd import statsd


stop_event = threading.Event()
log = get_log()
SEC_BETWEEN_RUNS = 1


def get_last_cursor():
    cursor = CursorManager.get()
    if not cursor:
        @retry(5, 0.2)
        def get_from_horizon():
            return Blockchain.get_last_cursor()
        cursor = get_from_horizon()
        log.info('got payment cursor from horizon', cursor=cursor)
        CursorManager.save(cursor)

    return cursor


def on_payment(address, payment):
    """handle a new payment from an address."""
    log.info('got payment', address=address, payment=payment)
    statsd.inc_count('payment_observed',
                     payment.amount,
                     tags=['app_id:%s' % payment.app_id,
                           'address:%s' % address])

    for watcher in Watcher.get_subscribed(address):
        enqueue_payment_callback(watcher.callback, address, payment)


def get_watching_addresses():
    """
    get a dict of address => watchers
    """
    addresses = {}
    for watcher in Watcher.get_all():
        for address in watcher.wallet_addresses:
            if address not in addresses:
                addresses[address] = []
            addresses[address].append(watcher)
    return addresses


def worker(stop_event):
    """Poll blockchain and apply callback on watched address. run until stopped."""
    cursor = 0
    while stop_event is None or not stop_event.is_set():
        time.sleep(SEC_BETWEEN_RUNS)
        start_t = time.time()
        try:
            addresses = get_watching_addresses()

            cursor = get_last_cursor()
            log.debug('got last cursor %s' % cursor)
            flow = TransactionFlow(cursor)
            for address, tx in flow.get_transactions(addresses):
                log.info('found transaction for address', address=address)
                payment = Blockchain.try_parse_payment(tx)
                if payment:
                    on_payment(address, payment)
                cursor = CursorManager.save(tx.paging_token)
            log.debug('save last cursor %s' % flow.cursor)
            # flow.cursor is the last block observed - it might not be a kin payment, 
            # so the previous .save inside the loop doesnt guarantee avoidance of reprocessing
            cursor = CursorManager.save(flow.cursor)
        except Exception as e:
            statsd.increment('watcher_beat.failed', tags=['error:%s' % e])
            log.exception('failed watcher iteration')
        statsd.timing('watcher_beat', time.time() - start_t)
        statsd.gauge('watcher_beat.cursor', cursor)
        report_queue_size()


def report_queue_size():
    try:
        from rq import Queue
        from .redis_conn import redis_conn
        q = Queue(connection=redis_conn)
        statsd.gauge('queue_size', q.count)
    except:
        pass


def init():
    """start a thread to watch the blockchain."""
    log.info('starting watcher service')
    t = threading.Thread(target=worker, args=(stop_event, ))
    t.daemon = True
    t.start()


def stop():
    stop_event.set()
