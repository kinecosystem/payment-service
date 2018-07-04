from . import config
from .log import get as get_log
from .models import Payment, Wallet
from kin import AccountExistsError, AccountNotFoundError, SDK
from .sdk_manager import read_only as read_only_sdk
from .errors import ParseError, WalletNotFoundError


log = get_log()
kin_sdk = read_only_sdk()


def create_wallet(funder: SDK, public_address: str, app_id: str, initial_xlm_amount: int = config.STELLAR_INITIAL_XLM_AMOUNT) -> None:
    """create a wallet."""
    try:
        account_exists = funder.check_account_exists(public_address)
    except Exception as e:
        log.info('failed checking wallet state', public_address=public_address)
    else:
        if account_exists:
            raise AccountExistsError

    log.info('creating wallet', public_address=public_address)

    memo = '1-{}'.format(app_id)
    tx_id = funder.create_account(public_address, initial_xlm_amount, memo)
    log.info('create wallet transaction', tx_id=tx_id)
    return tx_id


def get_wallet(public_address: str) -> Wallet:
    try:
        data = kin_sdk.get_account_data(public_address)
        return Wallet.from_blockchain(data, kin_sdk.kin_asset)
    except AccountNotFoundError:
        raise WalletNotFoundError('wallet %s not found' % public_address)


def pay_to(funder: SDK, public_address: str, amount: int, app_id: str, payment_id: str) -> Payment:
    """send kins to an address."""
    log.info('sending kin to', address=public_address)
    memo = Payment.create_memo(app_id, payment_id)
    tx_id = funder.send_kin(public_address, amount, memo_text=memo)
    return tx_id


def get_transaction_data(tx_id):
    data = kin_sdk.get_transaction_data(tx_id)
    return Payment.from_blockchain(data)


def try_parse_payment(tx_data):
    """try to parse payment from given tx_data. return None when failed."""
    try:
        return Payment.from_blockchain(tx_data)
    except ParseError as e:
        log.exception('failed to parse payment', tx_data=tx_data, error=e)
        return
    except Exception as e:
        log.exception('failed to parse payment', tx_data=tx_data, error=e)
        return
