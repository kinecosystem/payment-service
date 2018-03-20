import requests

from .blockchain import kin_sdk
from .log import get as get_log
from .models import Watcher, Payment
from .utils import retry


log = get_log()


def init():
    # on start, get all previous watchers from db and start monitoring
    # XXX should I have one single monitor?
    # XXX I need to start from the last known block/ fallback to X hours rewind
    # XXX upon receiving a relevant payment ship it to a queue and make sure
    # a worker will receive it and send it the watcher.callback
    for watcher in Watcher.get_all():
        start_monitor(watcher)


def start_monitor(watcher):
    def on_transaction(address, tx_data):
        try:
            payment = Payment.from_blockchain(tx_data)
        except ValueError as e:  # XXX memo not in right format - set a custom parsingMemoError
            log.exception('failed to parse payment', address=address, error=e)
            return
        except Exception as e:
            log.exception('failed to parse payment', address=address, tx_data=tx_data, error=e)
            return

        @retry(5, 0.2)
        def callback(payment):
            return requests.post(watcher.callback, json=payment.to_primitive()).json()

        response = callback(payment)
        log.info('callback response', response=response, service_id=watcher.service_id, payment=payment)

    log.info('starting monitor', watcher=watcher)

    if watcher.wallet_addresses:
        kin_sdk.monitor_accounts_kin_payments(watcher.wallet_addresses, on_transaction)  # XXX this starts a thread that I have no control over :(
