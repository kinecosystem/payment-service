import requests
import json
from .utils import lock, retry
from . import blockchain
from .models import Order
from queue import Queue
from threading import Thread
from .log import get as get_log
from .errors import OrderNotFoundError


log = get_log()


class PayQueue(object):
    def __init__(self, num_workers):
        self.q = Queue()
        for i in range(num_workers):
            t = Thread(target=self.worker)
            t.daemon = True
            t.start()

    def put(self, task):
        self.q.put(task)

    def worker(self):
        while True:
            try:
                item = self.q.get()
                do_work(item)
                self.q.task_done()
            except Exception as e:
                log.exception('worker failed with: {}'.format(e))


def do_work(payment):
    """lock, try to pay and callback."""
    with lock('payment:{}'.format(payment.order_id)):
        order = pay(payment)

        @retry(5, 0.2)
        def callback(order):
            return requests.post(payment.callback, json=order.to_primitive()).json()

        response = callback(order)
        log.info('callback response', response=response, order=order)


def pay(payment):
    try:
        order = Order.get(payment.order_id)
        log.info('order is already complete - not double spending', order=order)
        return order
    except OrderNotFoundError:
        pass

    log.info('trying to pay', order_id=payment.order_id)

    tx_id = blockchain.pay_to(payment.wallet_address, payment.amount,
                              payment.app_id, payment.order_id)

    log.info('payed transaction', tx_id=tx_id, order_id=payment.order_id)

    @retry(10, 3)
    def get_transaction_data(tx_id):
        return blockchain.get_transaction_data(tx_id)

    order = get_transaction_data(tx_id)
    order.save()

    log.info('order complete - submit back to callback payment.callback', order=order)

    return order
