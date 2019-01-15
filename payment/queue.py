import kin
from rq import Queue
import requests
from . import config
from .errors import PaymentNotFoundError, PersitentError
from .log import get as get_log
from .models import Payment, PaymentRequest, WalletRequest
from .utils import retry, lock
from .redis_conn import redis_conn
from .statsd import statsd
from .blockchain import Blockchain, get_sdk


q = Queue(connection=redis_conn)
log = get_log('rq.worker')


def enqueue_send_payment(payment_request: PaymentRequest):
    statsd.inc_count('transaction.enqueue',
                     payment_request.amount,
                     tags=['app_id:%s' % payment_request.app_id])
    result = q.enqueue(pay_and_callback, payment_request.to_primitive())
    log.info('enqueue result', result=result, payment_request=payment_request)


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


def enqueue_report_wallet_balance(root_wallet_address, channel_wallet_addresses):
    q.enqueue(
        report_balance,
        root_wallet_address,
        channel_wallet_addresses)


def enqueue_payment_callback(callback: str, wallet_address: str, value: Payment):
    __enqueue_callback(
        callback=callback,
        app_id=value.app_id,
        objekt='payment',
        state='success',
        action='send' if wallet_address == value.sender_address else 'receive',
        value=value.to_primitive())


def enqueue_payment_failed_callback(request: PaymentRequest, reason: str):
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
        value={'id': request.id})


def enqueue_wallet_failed_callback(request: WalletRequest, reason: str):
    __enqueue_callback(
        callback=request.callback,
        app_id=request.app_id,
        objekt='wallet',
        state='fail',
        action='create',
        value={'id': request.id, 'reason': reason})


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
    log.info('pay_and_callback recieved', payment_request=payment_request)
    payment_request = PaymentRequest(payment_request)
    with lock(redis_conn, 'payment:{}'.format(payment_request.id), blocking_timeout=120):
        try:
            payment = pay(payment_request)
        except kin.AccountNotActivatedError:
            enqueue_payment_failed_callback(payment_request, "no trustline")
        except Exception as e:
            enqueue_payment_failed_callback(payment_request, str(e))
            raise  # crash the job
        else:
            enqueue_payment_callback(payment_request.callback, payment.sender_address, payment)


def create_wallet_and_callback(wallet_request: dict):
    log.info('create_wallet_and_callback recieved', wallet_request=wallet_request)
    wallet_request = WalletRequest(wallet_request)

    @retry(10, 0.25, ignore=[kin.AccountExistsError, kin.LowBalanceError])
    def create_wallet(blockchain, wallet_request):
        return blockchain.create_wallet(wallet_request.wallet_address, wallet_request.app_id)

    try:
        with get_sdk(config.STELLAR_BASE_SEED) as blockchain:
            create_wallet(blockchain, wallet_request)
            enqueue_report_wallet_balance(blockchain.root_address, blockchain.channel_addresses)

    except kin.AccountExistsError:
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
        with get_sdk(config.STELLAR_BASE_SEED) as blockchain:
            tx_id = blockchain.pay_to(
                payment_request.recipient_address,
                payment_request.amount,
                payment_request.app_id,
                payment_request.id)
            enqueue_report_wallet_balance(blockchain.root_address, blockchain.channel_addresses)

        log.info('paid transaction', tx_id=tx_id, payment_id=payment_request.id)
        statsd.inc_count('transaction.paid',
                         payment_request.amount,
                         tags=['app_id:%s' % payment_request.app_id])
    except (kin.AccountNotFoundError, kin.AccountNotActivatedError) as e:
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


def report_balance(root_address, channel_addresses):
    """report root wallet balance metrics to statsd."""
    try:
        wallet = Blockchain.get_wallet(root_address)
        statsd.gauge('root_wallet.kin_balance', wallet.kin_balance,
                     tags=['address:%s' % root_address])
        statsd.gauge('root_wallet.native_balance', wallet.native_balance,
                     tags=['address:%s' % root_address])
        for channel_address in channel_addresses:
            wallet = Blockchain.get_wallet(channel_address)
            statsd.gauge('channel_wallet.native_balance', wallet.native_balance,
                         tags=['address:%s' % channel_address])

    except Exception:
        pass  # don't fail
