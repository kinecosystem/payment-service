from flask import Flask, request, jsonify
from .middleware import handle_errors
from .models import Order, WalletAddress, Payment
from . import blockchain
from .errors import AlreadyExistsError
from . import log
from kin import SdkHorizonError
from .queue import PayQueue


app = Flask(__name__)
pay_queue = PayQueue(10)
logger = log.init()


@app.route('/wallets', methods=['POST'])
@handle_errors
def create_wallet():
    body = WalletAddress(request.get_json())

    # wallet creation is idempotent - no locking needed
    # XXX should be async
    try:
        blockchain.create_wallet(body.wallet_address)
    except SdkHorizonError as e:
        if e.extras.result_codes.operations[0] == 'op_already_exists':
            logger.info('wallet already exists - ok')
            pass
        else:
            raise

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
    payment = Payment(request.get_json())

    try:
        Order.get(payment.order_id)
        raise AlreadyExistsError('order already exists')
    except KeyError:
        pass
    
    pay_queue.put(payment)
    return jsonify(), 201
