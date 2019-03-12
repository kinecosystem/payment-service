from . import config
from .log import init as init_log

log = init_log()
from flask import Flask, request, jsonify
from .transaction_flow import TransactionFlow
from .errors import AlreadyExistsError, PaymentNotFoundError, ServiceNotFoundError
from .middleware import handle_errors
from .models import Payment, WalletRequest, PaymentRequest, Service, WhitelistRequest, SubmitTransactionRequest
from .queue import enqueue_create_wallet, enqueue_send_payment, enqueue_submit_tx
from .blockchain import Blockchain, root_wallet

app = Flask(__name__)


@app.route('/wallets', methods=['POST'])
@handle_errors
def create_wallet():
    body = WalletRequest(request.get_json())
    body.validate()

    # wallet creation is idempotent - no locking needed
    enqueue_create_wallet(body)

    return jsonify(), 202


@app.route('/wallets/<wallet_address>', methods=['GET'])
@handle_errors
def get_wallet(wallet_address):
    w = Blockchain.get_wallet(wallet_address)
    return jsonify(w.to_primitive())


@app.route('/wallets/<wallet_address>/payments', methods=['GET'])
@handle_errors
def get_wallet_payments(wallet_address):
    payments = []
    flow = TransactionFlow(cursor=0)
    for tx in flow.get_address_transactions(wallet_address):
        payment = Blockchain.try_parse_payment(tx)
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
    payment.validate()
    try:
        Payment.get(payment.id)
        raise AlreadyExistsError('payment already exists')
    except PaymentNotFoundError:
        pass

    enqueue_send_payment(payment)
    return jsonify(), 201


@app.route('/services/<service_id>', methods=['PUT', 'DELETE'])
@handle_errors
def add_delete_service(service_id):
    body = request.get_json()
    if request.method == 'DELETE':
        service = Service.get(service_id)
        if not service:
            raise ServiceNotFoundError('didnt find service %s' % service_id) 
        service.delete()
    else:
        body['service_id'] = service_id
        service = Service(body)
        service.validate()
        service.save()

    return jsonify(service.to_primitive())


@app.route('/services/<service_id>/watchers/<address>/payments/<payment_id>', methods=['DELETE', 'PUT'])
@handle_errors
def add_delete_address_watcher(service_id, address, payment_id):
    service = Service.get(service_id)
    if not service:
        raise ServiceNotFoundError('didnt find service %s' % service_id) 

    if request.method == 'PUT':
        service.watch_payment(address, payment_id)
        log.info('added watcher', address=address)
    else:
        service.unwatch_payment(address, payment_id)
        log.info('deleted watcher', address=address)

    return jsonify({})


@app.route('/watchers', methods=['GET'])
@handle_errors
def get_watchers():
    watchers = {}
    for address, services in Service.get_all_watching_addresses().items():
        watchers[address] = [[s.service_id, s.callback] for s in services]

    return jsonify({'watchers': watchers})


@app.route('/tx/whitelist', methods=['POST'])
@handle_errors
def whitelist():
    whitelist_request = WhitelistRequest(request.get_json())
    whitelist_request.verify_transaction()
    # Transaction is verified, whitelist it and return to marketplace
    whitelisted_tx = whitelist_request.whitelist()
    return jsonify({'tx': whitelisted_tx}), 200


@app.route('/tx/submit', methods=['POST'])
@handle_errors
def whitelist_submit():
    network_id = root_wallet.read_sdk.environment.passphrase_hash
    log.info('request', request=request.get_json())
    submit_request = SubmitTransactionRequest(request.get_json())
    submit_request.validate()
    # submit_request.verify_transaction()
    enqueue_submit_tx(submit_request)
    return jsonify(), 201


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
                    'network_passphrase': config.STELLAR_NETWORK,
                    })
