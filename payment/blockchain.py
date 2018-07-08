import contextlib
import stellar_base
from typing import List
from kin.errors import AccountExistsError, AccountNotFoundError
from kin.sdk import Keypair, ChannelManager, SDK
from . import config
from .models import Payment, Wallet, TransactionRecord
from .utils import get_network_name
from .log import get as get_log
from .errors import ParseError, WalletNotFoundError


log = get_log()
_write_sdks = {}


def seed_to_address(seed: str) -> str:
    """convert seed to address."""
    return Keypair.from_seed(seed).address().decode()


def _init(seed='', channels=[]):
    kin_sdk = SDK(
        secret_key=seed,
        horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
        network=get_network_name(config.STELLAR_NETWORK),
        channel_secret_keys=channels,
        kin_asset=stellar_base.asset.Asset(config.STELLAR_KIN_TOKEN_NAME,
                                           config.STELLAR_KIN_ISSUER_ADDRESS))

    return kin_sdk


class Blockchain(object):
    read_sdk = _init()
    asset_code = read_sdk.kin_asset.code
    asset_issuer = read_sdk.kin_asset.issuer

    def __init__(self, sdk: SDK, root_address, channel_addresses):
        self.write_sdk = sdk
        self.root_address = root_address
        self.channel_addresses = channel_addresses

    def create_wallet(self, public_address: str, app_id: str,
                      initial_xlm_amount: int = config.STELLAR_INITIAL_XLM_AMOUNT) -> None:
        """create a wallet."""
        try:
            account_exists = self.write_sdk.check_account_exists(public_address)
        except Exception as e:
            log.info('failed checking wallet state', public_address=public_address)
        else:
            if account_exists:
                raise AccountExistsError

        log.info('creating wallet', public_address=public_address)

        memo = '1-{}'.format(app_id)
        tx_id = self.write_sdk.create_account(public_address, initial_xlm_amount, memo)
        log.info('create wallet transaction', tx_id=tx_id)
        return tx_id

    def pay_to(self, public_address: str, amount: int, app_id: str, payment_id: str) -> Payment:
        """send kins to an address."""
        log.info('sending kin to', address=public_address)
        memo = Payment.create_memo(app_id, payment_id)
        tx_id = self.write_sdk.send_kin(public_address, amount, memo_text=memo)
        return tx_id

    @staticmethod
    def get_wallet(public_address: str) -> Wallet:
        try:
            data = Blockchain.read_sdk.get_account_data(public_address)
            return Wallet.from_blockchain(data, Blockchain.read_sdk.kin_asset)
        except AccountNotFoundError:
            raise WalletNotFoundError('wallet %s not found' % public_address)

    @staticmethod
    def get_transaction_data(tx_id):
        data = Blockchain.read_sdk.get_transaction_data(tx_id)
        return Payment.from_blockchain(data)

    @staticmethod
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

    @staticmethod
    def get_address_records(address, cursor, limit=100) -> List[TransactionRecord]:
        log.debug('getting records from', address=address, cursor=cursor)
        reply = Blockchain.read_sdk.horizon.account_payments(
            address=address,
            params={'cursor': cursor,
                    'order': 'asc',
                    'limit': limit})
        records = [TransactionRecord(r, strict=False) for r in reply['_embedded']['records']]
        return records

    @staticmethod
    def get_all_records(cursor, limit=100) -> List[TransactionRecord]:
        log.debug('getting records from', cursor=cursor)
        reply = Blockchain.read_sdk.horizon.payments(
            params={'cursor': cursor,
                    'order': 'asc',
                    'limit': limit})
        records = [TransactionRecord(r, strict=False) for r in reply['_embedded']['records']]
        return records

    @staticmethod
    def get_last_cursor():
        reply = Blockchain.read_sdk.horizon.payments(params={'cursor': 'now', 'order': 'desc', 'limit': 1})
        return reply['_embedded']['records'][0]['paging_token']


# The wallet that funds all other channels and sub-funding-wallets
root_wallet = Blockchain(_init(config.STELLAR_BASE_SEED), seed_to_address(config.STELLAR_BASE_SEED), [])


@contextlib.contextmanager
def get_sdk(seed: str) -> Blockchain:
    from .channel_factory import get_channel
    global _write_sdks
    address = seed_to_address(seed)

    # find if this address already was initialized
    if address not in _write_sdks:
        _write_sdks[address] = _init(seed)
    sdk = _write_sdks[address]

    with get_channel(root_wallet) as channel:
        channels = [channel]
        sdk.channel_manager = ChannelManager(seed, channels, sdk.network, sdk.horizon)

        yield Blockchain(sdk, address, [seed_to_address(ch_seed) for ch_seed in channels])

    sdk.channel_manager = None
