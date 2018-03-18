import kin
from . import config
from .log import get as get_log
from .models import Payment, Wallet
from kin import SdkHorizonError


log = get_log()
kin_sdk = kin.SDK(
    base_seed=config.STELLAR_BASE_SEED,
    horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
    network=config.STELLAR_NETWORK,
    channel_seeds=config.STELLAR_CHANNEL_SEEDS)


def create_wallet(public_address: str, app_id: str) -> None:
    """create a wallet."""
    if kin_sdk.check_account_exists(public_address):
        log.info('wallet already exists - ok', public_address=public_address)
        return

    memo = '1-{}'.format(app_id)
    initial_xlm_amount = config.STELLAR_INITIAL_XLM_AMOUNT
    try:
        tx_id = kin_sdk.create_account(
            public_address, starting_balance=initial_xlm_amount, memo_text=memo)
        log.info('create wallet transaction', tx_id=tx_id)
    except SdkHorizonError as e:
        if e.extras.result_codes.operations[0] == 'op_already_exists':
            log.info('wallet already exists - ok', public_address=public_address)
        else:
            raise


def get_wallet(public_address: str) -> Wallet:
    data = kin_sdk.get_account_data(public_address)
    return Wallet.from_blockchain(data, kin_sdk.kin_asset)


def pay_to(public_address: str, amount: int, app_id: str, payment_id: str) -> Payment:
    """send kins to an address."""
    log.info('sending kin to', address=public_address)
    memo = Payment.create_memo(app_id, payment_id)
    tx_id = kin_sdk.send_kin(public_address, amount, memo_text=memo)
    return tx_id


def get_transaction_data(tx_id):
    data = kin_sdk.get_transaction_data(tx_id)
    return Payment.from_blockchain(data)
