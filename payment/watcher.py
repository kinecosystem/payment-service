from .blockchain import kin_sdk
from .models import Watcher, Payment
from .log import get as get_log
import requests


log = get_log()


def init():
    for watcher in Watcher.get_all():
        start_monitor(watcher)


def start_monitor(watcher):
    def callback(address, tx_data):
        payment = Payment.from_blockchain(tx_data)
        response = requests.post(watcher.callback, json=payment.to_primitive()).json()
        log.info('callback response', response=response, service_id=watcher.service_id, payment=payment)
    kin_sdk.monitor_accounts_kin_payments(watcher.wallet_addresses, callback)  # XXX this starts a thread that I have no control over :(
