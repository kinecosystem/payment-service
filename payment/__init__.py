from flask import Flask, request, jsonify
from .middleware import handle_errors
from .models import Order, WalletAddress, Payment
from .utils import lock
from . import blockchain
from .errors import AlreadyExistsError
from . import log
from kin import SdkHorizonError


app = Flask(__name__)
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
    t = Order.get(order_id)
    return jsonify(t.to_primitive())


@app.route('/orders', methods=['POST'])
@handle_errors
def pay():
    payment = Payment(request.get_json())

    try:
        t = Order.get(payment.order_id)
        raise AlreadyExistsError('order already exists')
    except KeyError:
        pass

    # XXX should be async
    with lock('payment:{}'.format(payment.order_id)):
        try:
            t = Order.get(payment.order_id)
            return jsonify(t.to_primitive())
        except KeyError:
            pass

        tx_id = blockchain.pay_to(payment.wallet_address, payment.amount,
                                  payment.app_id, payment.order_id)
        for i in range(3):
            try:
                t = blockchain.get_transaction_data(tx_id)
                t.save()
                break
            except Exception:
                if i == 2:
                    raise
                else:
                    time.sleep(0.1)

        return jsonify(t.to_primitive())
