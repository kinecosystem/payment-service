import kin
from . import config
from .log import get as get_log
from .models import Payment, Wallet
from kin import AccountExistsError


log = get_log()
kin_sdk = kin.SDK(
    secret_key=config.STELLAR_BASE_SEED,
    horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
    network=config.STELLAR_NETWORK,
    channel_secret_keys=config.STELLAR_CHANNEL_SEEDS)


def create_wallet(public_address: str, app_id: str) -> None:
    """create a wallet."""
    try:
        if kin_sdk.check_account_exists(public_address):
            log.info('wallet already exists - ok', public_address=public_address)
            return
    except Exception as e:
        log.info('failed checking wallet state', public_address=public_address)

    log.info('creating wallet', public_address=public_address)

    memo = '1-{}'.format(app_id)
    initial_xlm_amount = config.STELLAR_INITIAL_XLM_AMOUNT
    try:
        tx_id = kin_sdk.create_account(
            public_address, starting_balance=initial_xlm_amount, memo_text=memo)
        log.info('create wallet transaction', tx_id=tx_id)
    except AccountExistsError as e:
        log.info('wallet already exists - ok', public_address=public_address)
    except Exception as e:
        log.exception('failed creating wallet', error=str(e), public_address=public_address)
        raise Exception(str(e))  # kinSdk bug causes the process to crash with their exceptions



def get_wallet(public_address: str) -> Wallet:
    try:
        data = kin_sdk.get_account_data(public_address)
    except Exception as e:
        raise Exception(str(e))  # kinSdk bug causes the process to crash with their exceptions
    return Wallet.from_blockchain(data, kin_sdk.kin_asset)


def pay_to(public_address: str, amount: int, app_id: str, payment_id: str) -> Payment:
    """send kins to an address."""
    log.info('sending kin to', address=public_address)
    memo = Payment.create_memo(app_id, payment_id)
    try:
        tx_id = kin_sdk.send_kin(public_address, amount, memo_text=memo)
    except Exception as e:
        raise Exception(str(e))  # kinSdk bug causes the process to crash with their exceptions
    return tx_id


def get_transaction_data(tx_id):
    try:
        data = kin_sdk.get_transaction_data(tx_id)
    except Exception as e:
        raise Exception(str(e))  # kinSdk bug causes the process to crash with their exceptions
    return Payment.from_blockchain(data)
