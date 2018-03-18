import requests
from .utils import lock, retry
from . import blockchain
from .models import Payment
from queue import Queue
from threading import Thread
from .log import get as get_log
from .errors import PaymentNotFoundError


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


def do_work(payment_request):
    """lock, try to pay and callback."""
    with lock('payment:{}'.format(payment_request.id)):
        # XXX maybe separate this into 2 tasks - 1 pay, 2 callback
        payment = pay(payment_request)

        @retry(5, 0.2)
        def callback(payment, payment_request):
            return requests.post(payment_request.callback, json=payment.to_primitive()).json()

        response = callback(payment, payment_request)
        log.info('callback response', response=response, payment=payment)


def pay(payment_request):
    try:
        payment = Payment.get(payment_request.id)
        log.info('payment is already complete - not double spending', payment=payment)
        return payment
    except PaymentNotFoundError:
        pass

    log.info('trying to pay', payment_id=payment_request.id)

    tx_id = blockchain.pay_to(payment_request.recipient_address,
                              payment_request.amount,
                              payment_request.app_id,
                              payment_request.id)

    log.info('payed transaction', tx_id=tx_id, payment_id=payment_request.id)

    @retry(10, 3)
    def get_transaction_data(tx_id):
        return blockchain.get_transaction_data(tx_id)

    payment = get_transaction_data(tx_id)
    payment.save()

    log.info('payment complete - submit back to callback payment.callback', payment=payment)

    return payment
