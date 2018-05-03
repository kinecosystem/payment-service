import requests
import time

from .blockchain import kin_sdk
from .log import get as get_log
from .models import Watcher, Payment, CursorManager
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


def on_transaction(address, tx_data):
    """handle a new transaction from an address."""
    try:
        payment = Payment.from_blockchain(tx_data)
        log.info('got payment', address=address, payment=payment)
    except ValueError as e:  # XXX memo not in right format - set a custom parsingMemoError
        log.exception('failed to parse payment', address=address, error=e)
        return
    except Exception as e:
        log.exception('failed to parse payment', address=address, tx_data=tx_data, error=e)
        return

    @retry(5, 0.2)
    def callback(watcher):
        res = requests.post(watcher.callback, json=payment.to_primitive())
        res.raise_for_status()
        return res.json()

    for watcher in Watcher.get_subscribed(address):
        try:
            response = callback(watcher)
            log.info('callback response', response=response, service_id=watcher.service_id, payment=payment)
        except Exception as e:
            log.error('callback failed', error=e, service_id=watcher.service_id, payment=payment)


def wrapped_get_transaction_data(tx_id):
    try:
        return kin_sdk.get_transaction_data(tx_id)
    except Exception as e:
        raise Exception(str(e))  # kinSdk bug causes the process to crash with their exceptions


class TransactionFlow():
    """class that saves the last cursor when getting transactions."""
    def __init__(self, cursor):
        self.cursor = cursor

    def get_transactions(self, addresses):
        """get transactions for given addresses from the given cursor"""
        def get_records(cursor):
            log.debug('getting records from', cursor=cursor)
            reply = kin_sdk.horizon.payments(params={
                'cursor': cursor,
                'order': 'asc',
                'limit': 100})
            records = reply['_embedded']['records']
            log.debug('got records', num=len(records), cursor=cursor)
            return records

        records = get_records(self.cursor)
        while records:
            for record in records:
                if (record['type'] == 'payment'
                        and record.get('asset_code') == kin_sdk.kin_asset.code
                        and record.get('asset_issuer') == kin_sdk.kin_asset.issuer):

                    if record['to'] in addresses:
                        yield record['to'], wrapped_get_transaction_data(record['transaction_hash'])
                    elif record['from'] in addresses:
                        yield record['from'], wrapped_get_transaction_data(record['transaction_hash'])
                    # else - address is not watched
                self.cursor = record['paging_token']
            records = get_records(self.cursor)


def worker(stop_event):
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
                on_transaction(address, tx)
                CursorManager.save(tx['paging_token'])
            log.debug('save last cursor %s' % flow.cursor)
            CursorManager.save(flow.cursor)
        except Exception as e:
            log.exception('failed worker iteration', error=e)


def init():
    log.info('starting watcher service')
    t = threading.Thread(target=worker, args=(stop_event, ))
    t.daemon = True
    t.start()


def stop():
    stop_event.set()
    

if __name__ == '__main__':
    while True:
        try:
            time.sleep(0.1)
        except KeyboardInterrupt:
            stop()
            print('ended nicely')
            break
