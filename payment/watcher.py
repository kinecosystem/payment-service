import requests
import time

from .blockchain import kin_sdk
from .transaction_flow import TransactionFlow
from .log import get as get_log
from .models import Payment, Watcher, CursorManager
from .utils import retry
import threading


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
    @retry(5, 0.2)
    def callback(watcher):
        res = requests.post(watcher.callback, json=payment.to_primitive())
        res.raise_for_status()
        return res.json()

    log.info('got payment', address=address, payment=payment)

    for watcher in Watcher.get_subscribed(address):
        try:
            response = callback(watcher)
            log.info('callback response', response=response, service_id=watcher.service_id, payment=payment)
        except Exception as e:
            log.error('callback failed', error=e, service_id=watcher.service_id, payment=payment)


def worker(stop_event):
    """Poll blockchain and apply callback on watched address. run until stopped."""
    while not stop_event.is_set():
        time.sleep(SEC_BETWEEN_RUNS)
        try:
            # get a dict of address => watchers
            addresses = {}
            for watcher in Watcher.get_all():
                for address in watcher.wallet_addresses:
                    if address not in addresses:
                        addresses[address] = []
                    addresses[address].append(watcher)

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
            CursorManager.save(flow.cursor)
        except Exception as e:
            log.exception('failed worker iteration', error=e)


def try_parse_payment(tx_data):
    """try to parse payment from given tx_data. return None when failed."""
    try:
        return Payment.from_blockchain(tx_data)
    except ValueError as e:  # XXX memo not in right format - set a custom parsingMemoError
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
