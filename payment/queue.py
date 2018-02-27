import requests
import json
from .utils import lock, retry
from . import blockchain
from .models import Order
from queue import Queue
from threading import Thread


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
            item = self.q.get()
            do_work(item)
            self.q.task_done()


def do_work(payment):
    with lock('payment:{}'.format(payment.order_id)):
        def pay():
            try:
                order = Order.get(payment.order_id)
                print('order is already complete - not double spending: {}'.format(order))
                return json.dumps(order.to_primitive())
            except KeyError:
                pass

            tx_id = blockchain.pay_to(payment.wallet_address, payment.amount,
                                      payment.app_id, payment.order_id)

            @retry(3)
            def get_transaction_data(tx_id):
                return blockchain.get_transaction_data(tx_id)

            order = get_transaction_data(tx_id)
            order.save()

            print('order complete - submit back to callback payment.callback: {}'.format(order))

            return json.dumps(order.to_primitive())

        order = pay()

        @retry(3)
        def callback():
            return requests.get(payment.callback).json()
        response = callback() 
        print('callback response: {}'.format(response))
