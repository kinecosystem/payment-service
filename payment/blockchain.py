import kin
from . import config
from .models import Transaction


kin_sdk = kin.SDK(
    base_seed=config.STELLAR_BASE_SEED,
    horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
    network=config.STELLAR_NETWORK,
    channel_seeds=config.STELLAR_CHANNEL_SEEDS)


def create_wallet(public_address: str) -> None:
    """create a wallet."""
    initial_xlm_amount = config.STELLAR_INITIAL_XLM_AMOUNT
    tx_id = kin_sdk.create_account(public_address, starting_balance=initial_xlm_amount)
    print("received tx_id: {}".format(tx_id))


def pay_to(public_address: str, amount: int, app_id: str, order_id: str) -> Transaction:
    '''send kins to an address'''
    print('sending kin to address: {}'.format(public_address))
    memo = Transaction.create_memo(app_id, order_id)
    tx_id = kin_sdk.send_kin(public_address, amount, memo)
    data = kin_sdk.get_transaction_data(tx_id)
    return Transaction.from_blockchain(data)
