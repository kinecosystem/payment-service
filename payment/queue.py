from rq import Queue
import requests
from . import blockchain
from .errors import PaymentNotFoundError
from .log import get as get_log
from .models import Payment, PaymentRequest
from .utils import lock, retry
from .redis_conn import redis_conn
from .statsd import statsd


q = Queue(connection=redis_conn)
log = get_log()


def enqueue(payment_request):
    statsd.increment('transaction.enqueue',
                     tags=['app_id:%s' % payment_request.app_id])
    statsd.histogram('transaction.enqueue',
                     payment_request.amount,
                     tags=['app_id:%s' % payment_request.app_id])
    result = q.enqueue(pay_and_callback, payment_request.to_primitive())
    log.info('enqueue result', result=result, payment_request=payment_request)


def pay_and_callback(payment_request):
    """lock, try to pay and callback."""
    log.info('pay_and_callback recieved', payment_request=payment_request)
    payment_request = PaymentRequest(payment_request)
    with lock(redis_conn, 'payment:{}'.format(payment_request.id)):
        # XXX maybe separate this into 2 tasks - 1 pay, 2 callback
        payment = pay(payment_request)

        @retry(5, 0.2)
        def callback(payment, payment_request):
            res = requests.post(payment_request.callback, json=payment.to_primitive())
            res.raise_for_status()
            return res.json()

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

    # XXX retry on retriable errors
    try:
        tx_id = blockchain.pay_to(payment_request.recipient_address,
                                  payment_request.amount,
                                  payment_request.app_id,
                                  payment_request.id)
        log.info('paid transaction', tx_id=tx_id, payment_id=payment_request.id)
        statsd.increment('transaction.paid',
                         tags=['app_id:%s' % payment_request.app_id])
        statsd.histogram('transaction.paid',
                         payment_request.amount,
                         tags=['app_id:%s' % payment_request.app_id])
    except Exception as e:
        log.exception('failed to pay transaction', error=e, tx_id=tx_id, payment_id=payment_request.id)
        statsd.increment('transaction.failed',
                         tags=['app_id:%s' % payment_request.app_id])

    @retry(10, 3)
    def get_transaction_data(tx_id):
        return blockchain.get_transaction_data(tx_id)

    payment = get_transaction_data(tx_id)
    payment.save()

    log.info('payment complete - submit back to callback payment.callback', payment=payment)

    return payment
