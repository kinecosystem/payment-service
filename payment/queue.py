from typing import Union
from rq import Queue
import requests

from . import config
from .errors import PaymentNotFoundError, PersitentError
from .log import get as get_log
from .models import Payment, PaymentRequest, WalletRequest, SubmitTransactionRequest
from .utils import retry, lock
from .redis_conn import redis_conn
from .statsd import statsd
from .blockchain import Blockchain, get_sdk, root_account
from kin import KinErrors, Builder

q = Queue(connection=redis_conn)
log = get_log('rq.worker')


def enqueue_send_payment(payment_request: PaymentRequest):
    statsd.inc_count('transaction.enqueue',
                     payment_request.amount,
                     tags=['app_id:%s' % payment_request.app_id])
    result = q.enqueue(pay_and_callback, payment_request.to_primitive())
    log.info('enqueue result', result=result, payment_request=payment_request)


def enqueue_submit_tx(submit_request: SubmitTransactionRequest):
    # statsd.inc_count('transaction.enqueue',
    #                 payment_request.amount,
    #                 tags=['app_id:%s' % payment_request.app_id])
    result = q.enqueue(submit_tx_callback, submit_request.to_primitive())
    log.info('enqueue result', result=result, submit_request=submit_request)


def enqueue_create_wallet(wallet_request: WalletRequest):
    statsd.increment('wallet_creation.enqueue',
                     tags=['app_id:%s' % wallet_request.app_id])

    result = q.enqueue(create_wallet_and_callback, wallet_request.to_primitive())
    log.info('enqueue result', result=result, wallet_request=wallet_request)


def __enqueue_callback(callback: str, app_id: str, objekt: str, state: str, action: str, value: dict):
    statsd.increment('callback.enqueue',
                     tags=['app_id:%s' % app_id,
                           'object:%s' % objekt,
                           'state:%s' % state,
                           'action:%s' % action])

    result = q.enqueue(call_callback,
                       callback,
                       app_id,
                       objekt=objekt,
                       state=state,
                       action=action,
                       value=value)
    log.info('enqueue result', result=result, value=value)


def enqueue_report_wallet_balance(root_wallet_address):
    q.enqueue(report_balance, root_wallet_address, [])


def enqueue_payment_callback(callback: str, value: Payment, action: str):
    __enqueue_callback(
        callback=callback,
        app_id=value.app_id,
        objekt='payment',
        state='success',
        action=action,
        value=value.to_primitive())


def enqueue_payment_failed_callback(request: Union[PaymentRequest, SubmitTransactionRequest] , reason: str):
    __enqueue_callback(
        callback=request.callback,
        app_id=request.app_id,
        objekt='payment',
        state='fail',
        action='send',
        value={'id': request.id, 'reason': reason})


def enqueue_wallet_callback(request: WalletRequest):
    __enqueue_callback(
        callback=request.callback,
        app_id=request.app_id,
        objekt='wallet',
        state='success',
        action='create',
        value={'id': request.id, 'wallet_address': request.wallet_address})


def enqueue_wallet_failed_callback(request: WalletRequest, reason: str):
    __enqueue_callback(
        callback=request.callback,
        app_id=request.app_id,
        objekt='wallet',
        state='fail',
        action='create',
        value={'id': request.id, 'reason': reason, 'wallet_address': request.wallet_address})


def call_callback(callback: str, app_id: str, objekt: str, state: str, action: str, value: dict):
    @retry(5, 0.2)
    def retry_callback(callback: str, payload: dict):
        res = requests.post(callback, json=payload)
        res.raise_for_status()
        return res.json()

    payload = {
        'object': objekt,
        'state': state,
        'action': action,
        'value': value,
    }

    tags = ['app_id:%s' % app_id,
            'object:%s' % objekt,
            'state:%s' % state,
            'action:%s' % action]
    try:
        response = retry_callback(callback, payload)
        statsd.increment('callback.success', tags=tags)
        log.info('callback response', response=response, payload=payload)
    except Exception as e:
        statsd.increment('callback.failed', tags=tags)
        log.exception('callback failed', payload=payload)
        raise


def pay_and_callback(payment_request: dict):
    """lock, try to pay and callback."""
    log.info('pay_and_callback received', payment_request=payment_request)
    payment_request = PaymentRequest(payment_request)
    with lock(redis_conn, 'payment:{}'.format(payment_request.id), blocking_timeout=120):
        try:
            payment = pay(payment_request)
        except Exception as e:
            enqueue_payment_failed_callback(payment_request, str(e))
            raise  # crash the job
        else:
            enqueue_payment_callback(payment_request.callback, payment, 'send')


def submit_tx_callback(submit_request: dict):
    """lock, try to pay and callback."""
    log.info('submit_tx_callback received', submit_request=submit_request)
    submit_request = SubmitTransactionRequest(submit_request)
    tx_builder = Builder.import_from_xdr(submit_request.xdr)
    tx_builder.sign(config.STELLAR_BASE_SEED)
    tx_builder.network = submit_request.network_id # The XDR doesn't include the network id
    with lock(redis_conn, 'submit:{}'.format(submit_request.id), blocking_timeout=120):
        try:
            tx_id = root_account.submit_transaction(tx_builder)
        except Exception as e:
            enqueue_payment_failed_callback(submit_request, str(e))
            raise  # crash the job
        else:
            payment = Payment.from_payment_request(submit_request, submit_request.sender_address, tx_id)
            enqueue_payment_callback(submit_request.callback, payment, 'receive')


def create_wallet_and_callback(wallet_request: dict):
    log.info('create_wallet_and_callback received', wallet_request=wallet_request)
    wallet_request = WalletRequest(wallet_request)

    @retry(10, 0.25, ignore=[KinErrors.AccountExistsError, KinErrors.LowBalanceError])
    def create_wallet(blockchain, wallet_request):
        return blockchain.create_wallet(wallet_request.wallet_address)

    try:
        with get_sdk(config.STELLAR_BASE_SEED, wallet_request.app_id) as blockchain:
            create_wallet(blockchain, wallet_request)
            enqueue_report_wallet_balance(blockchain.root_address)

    except KinErrors.AccountExistsError:
        statsd.increment('wallet.exists', tags=['app_id:%s' % wallet_request.app_id])
        enqueue_wallet_failed_callback(wallet_request, "account exists")
        log.info('wallet already exists - ok', public_address=wallet_request.wallet_address)

    except Exception as e:
        statsd.increment('wallet.failed', tags=['app_id:%s' % wallet_request.app_id])
        enqueue_wallet_failed_callback(wallet_request, str(e))
        log.exception('failed to create wallet', wallet_id=wallet_request.id)
        raise  # crash the job

    else:
        statsd.increment('wallet.created', tags=['app_id:%s' % wallet_request.app_id])
        enqueue_wallet_callback(wallet_request)


def pay(payment_request: PaymentRequest):
    """pays only if not already paid."""
    try:
        payment = Payment.get(payment_request.id)
        log.info('payment is already complete - not double spending', payment=payment)
        return payment
    except PaymentNotFoundError:
        pass

    log.info('trying to pay', payment_id=payment_request.id)

    # XXX retry on retry-able errors
    try:
        with get_sdk(config.STELLAR_BASE_SEED, payment_request.app_id) as blockchain:
            tx_id = blockchain.pay_to(
                payment_request.recipient_address,
                payment_request.amount,
                payment_request.id)
            enqueue_report_wallet_balance(blockchain.root_address)

        log.info('paid transaction', tx_id=tx_id, payment_id=payment_request.id)
        statsd.inc_count('transaction.paid',
                         payment_request.amount,
                         tags=['app_id:%s' % payment_request.app_id])
    except (KinErrors.AccountNotFoundError, KinErrors.AccountNotActivatedError, KinErrors.RequestError) as e:
        raise PersitentError(e)
    except Exception as e:
        statsd.increment('transaction.failed',
                         tags=['app_id:%s' % payment_request.app_id])
        log.exception('failed to pay transaction', payment_id=payment_request.id)
        raise

    payment = Payment.from_payment_request(payment_request, blockchain.root_address, tx_id)
    payment.save()

    log.info('payment complete - submit back to callback payment.callback', payment=payment)

    return payment


def report_balance(root_address, channel_addresses=[]):
    """report root wallet balance metrics to statsd."""
    try:
        wallet = Blockchain.get_wallet(root_address)
        statsd.gauge('root_wallet.kin_balance', wallet.kin_balance,
                     tags=['address:%s' % root_address])
        statsd.gauge('root_wallet.native_balance', wallet.native_balance,
                     tags=['address:%s' % root_address])
    except Exception:
        pass  # don't fail
