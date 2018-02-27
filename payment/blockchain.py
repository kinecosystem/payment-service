import kin
from . import config
from .log import get as get_log
from .models import Order, Wallet


log = get_log()
kin_sdk = kin.SDK(
    base_seed=config.STELLAR_BASE_SEED,
    horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
    network=config.STELLAR_NETWORK,
    channel_seeds=config.STELLAR_CHANNEL_SEEDS)


def create_wallet(public_address: str) -> None:
    """create a wallet."""
    initial_xlm_amount = config.STELLAR_INITIAL_XLM_AMOUNT
    tx_id = kin_sdk.create_account(public_address, starting_balance=initial_xlm_amount)
    log.info('create wallet transaction', tx_id=tx_id)


def get_wallet(public_address: str) -> Wallet:
    data = kin_sdk.get_account_data(public_address)
    return Wallet.from_blockchain(data, kin_sdk.kin_asset)


def pay_to(public_address: str, amount: int, app_id: str, order_id: str) -> Order:
    """send kins to an address"""
    log.info('sending kin to', address=public_address)
    memo = Order.create_memo(app_id, order_id)
    tx_id = kin_sdk.send_kin(public_address, amount, memo)
    return tx_id


def get_transaction_data(tx_id):
    data = kin_sdk.get_transaction_data(tx_id)
    return Order.from_blockchain(data)
