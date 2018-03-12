from flask import Flask, request, jsonify
from .middleware import handle_errors
from .models import Order, WalletRequest, OrderRequest, Watcher
from . import blockchain
from .errors import AlreadyExistsError, OrderNotFoundError
from .log import init as init_log
from .queue import PayQueue
from . import watcher as watcher_service


app = Flask(__name__)
pay_queue = PayQueue(10)
log = init_log()


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


@app.route('/orders/<order_id>', methods=['GET'])
@handle_errors
def get_order(order_id):
    order = Order.get(order_id)
    return jsonify(order.to_primitive())


@app.route('/orders', methods=['POST'])
@handle_errors
def pay():
    payment = OrderRequest(request.get_json())

    try:
        Order.get(payment.order_id)
        raise AlreadyExistsError('order already exists')
    except OrderNotFoundError:
        pass
    
    pay_queue.put(payment)
    return jsonify(), 201


@app.route('/watcher/<service_id>', methods=['PUT'])
@handle_errors
def watch(service_id):
    body = request.get_json()
    body['service_id'] = service_id
    watcher = Watcher(body)
    watcher.save()
    watcher_service.start_watcher(watcher)

    return jsonify(), 201
