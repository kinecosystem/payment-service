from flask import Flask, request, jsonify
from .middleware import handle_errors
from .models import Payment, WalletRequest, PaymentRequest, Watcher
from . import blockchain
from .errors import AlreadyExistsError, PaymentNotFoundError
from .log import init as init_log
from .queue import PayQueue
from . import watcher as watcher_service


app = Flask(__name__)
pay_queue = PayQueue(2)
log = init_log()
watcher_service.init()


@app.route('/wallets', methods=['POST'])
@handle_errors
def create_wallet():
    body = WalletRequest(request.get_json())

    # wallet creation is idempotent - no locking needed
    # XXX should be async
    blockchain.create_wallet(body.wallet_address, body.app_id)

    return jsonify(), 202


@app.route('/wallets/<wallet_address>', methods=['GET'])
@handle_errors
def get_wallet(wallet_address):
    w = blockchain.get_wallet(wallet_address)
    return jsonify(w.to_primitive())


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
    
    pay_queue.put(payment)
    return jsonify(), 201


@app.route('/watchers/<service_id>', methods=['PUT'])
@handle_errors
def watch(service_id):
    body = request.get_json()
    body['service_id'] = service_id
    watcher = Watcher(body)
    watcher.save()
    watcher_service.start_monitor(watcher)

    return jsonify(watcher.to_primitive())
