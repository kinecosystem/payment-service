from flask import Flask, request, jsonify
from .middleware import handle_errors
from .models import Transaction
from .utils import lock
from . import blockchain


app = Flask(__name__)


@app.route('/wallets/', methods=['POST'])
@handle_errors
def create_wallet():
    body = request.get_json()
    wallet_address = body['wallet_address']

    # wallet creation is idempotent - no locking needed
    blockchain.create_wallet(wallet_address)

    return jsonify(), 201


@app.route('/orders/<order_id>', methods=['GET'])
@handle_errors
def get_order(order_id):
    t = Transaction.get_by_order_id(order_id)
    return jsonify(t.to_primitive())


@app.route('/orders/', methods=['POST'])
@handle_errors
def pay():
    body = request.get_json()
    order_id = body['order_id']
    app_id = body['app_id']
    wallet_address = body['wallet_address']
    amount = body['amount']

    # double checked locking
    try:
        t = Transaction.get_by_order_id(order_id)
        return jsonify(t.to_primitive())
    except KeyError:
        pass

    with lock('payment:{}'.format(order_id)):
        try:
            t = Transaction.get_by_order_id(order_id)
            return jsonify(t.to_primitive())
        except KeyError:
            pass

        t = blockchain.pay_to(wallet_address, amount, app_id, order_id)
        t.save()

        return jsonify(t.to_primitive())
