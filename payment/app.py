from . import config
from .log import init as init_log

log = init_log()
from flask import Flask, request, jsonify
from . import blockchain
from .transaction_flow import TransactionFlow
from .errors import AlreadyExistsError, PaymentNotFoundError
from .middleware import handle_errors
from .models import Payment, WalletRequest, PaymentRequest, Watcher
from .queue import enqueue_create_wallet, enqueue_send_payment
from .utils import get_network_passphrase

app = Flask(__name__)


@app.route('/wallets', methods=['POST'])
@handle_errors
def create_wallet():
    body = WalletRequest(request.get_json())

    # wallet creation is idempotent - no locking needed
    enqueue_create_wallet(body)

    return jsonify(), 202


@app.route('/wallets/<wallet_address>', methods=['GET'])
@handle_errors
def get_wallet(wallet_address):
    w = blockchain.get_wallet(wallet_address)
    return jsonify(w.to_primitive())


@app.route('/wallets/<wallet_address>/payments', methods=['GET'])
@handle_errors
def get_wallet_payments(wallet_address):
    payments = []
    flow = TransactionFlow(cursor=0)
    for tx in flow.get_address_transactions(wallet_address):
        payment = blockchain.try_parse_payment(tx)
        if payment:
            payments.append(payment.to_primitive())

    return jsonify({'payments': payments})


@app.route('/payments/<payment_id>', methods=['GET'])
@handle_errors
def get_payment(payment_id):
    payment = Payment.get(payment_id)
    return jsonify(payment.to_primitive())


@app.route('/payments', methods=['POST'])
@handle_errors
def pay():
    payment = PaymentRequest(request.get_json())
    try:
        Payment.get(payment.id)
        raise AlreadyExistsError('payment already exists')
    except PaymentNotFoundError:
        pass

    enqueue_send_payment(payment)
    return jsonify(), 201


@app.route('/watchers/<service_id>', methods=['PUT', 'POST'])
@handle_errors
def watch(service_id):
    body = request.get_json()
    body['service_id'] = service_id
    if request.method == 'PUT':
        watcher = Watcher(body)
    else:
        watcher = Watcher.get(service_id)
        if watcher:
            watcher.add_addresses(body['wallet_addresses'])
        else:
            watcher = Watcher(body)

    watcher.save()
    log.info('added watcher', watcher=watcher)

    return jsonify(watcher.to_primitive())


@app.route('/status', methods=['GET'])
def status():
    body = request.get_json()
    log.info('status received', body=body)
    return jsonify({'app_name': config.APP_NAME,
                    'status': 'ok',
                    'start_time': config.build['start_time'],
                    'build': {'timestamp': config.build['timestamp'],
                              'commit': config.build['commit']}})


@app.route('/config', methods=['GET'])
def get_config():
    return jsonify({'horizon_url': config.STELLAR_HORIZON_URL,
                    'network_passphrase': get_network_passphrase(config.STELLAR_NETWORK),
                    'asset_issuer': config.STELLAR_KIN_ISSUER_ADDRESS,
                    'asset_code': config.STELLAR_KIN_TOKEN_NAME,
                    })
