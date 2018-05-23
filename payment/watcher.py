import threading
import time

from .blockchain import kin_sdk
from .queue import call_callback
from .errors import ParseError
from .log import get as get_log
from .models import Payment, Watcher, CursorManager
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
            reply = kin_sdk.horizon.payments(params={'cursor': 'now', 'order': 'desc', 'limit': 1})
            return reply['_embedded']['records'][0]['paging_token']
        cursor = get_from_horizon()
        log.info('got payment cursor from horizon', cursor=cursor)
        CursorManager.save(cursor)

    return cursor


def on_payment(address, payment):
    """handle a new payment from an address."""
    log.info('got payment', address=address, payment=payment)
    statsd.histogram('payment_observed',
                     payment.amount,
                     tags=['app_id:%s' % payment.app_id,
                           'address:%s' % address])

    for watcher in Watcher.get_subscribed(address):
        call_callback(watcher.callback, payment.to_primitive())


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
                payment = try_parse_payment(tx)
                if payment:
                    on_payment(address, payment)
                CursorManager.save(tx['paging_token'])
            log.debug('save last cursor %s' % flow.cursor)
            # flow.cursor is the last block observed - it might not be a kin payment, 
            # so the previous .save inside the loop doesnt guarantee avoidance of reprocessing
            CursorManager.save(flow.cursor)
        except Exception as e:
            log.exception('failed worker iteration', error=e)
        statsd.timing('worker_beat', time.time() - start_t)


def try_parse_payment(tx_data):
    """try to parse payment from given tx_data. return None when failed."""
    try:
        return Payment.from_blockchain(tx_data)
    except ParseError as e:
        log.exception('failed to parse payment', tx_data=tx_data, error=e)
        return
    except Exception as e:
        log.exception('failed to parse payment', tx_data=tx_data, error=e)
        return


def init():
    """start a thread to watch the blockchain."""
    log.info('starting watcher service')
    t = threading.Thread(target=worker, args=(stop_event, ))
    t.daemon = True
    t.start()


def stop():
    stop_event.set()
