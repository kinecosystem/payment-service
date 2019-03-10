import contextlib
# import stellar_base
from typing import List
# from kin.errors import AccountExistsError, AccountNotFoundError
# from kin.stellar.horizon_models import TransactionData
# from kin.sdk import Keypair, ChannelManager, SDK

from kin.errors import AccountNotFoundError
from kin.transactions import SimplifiedTransaction
from kin import KinClient
from kin.account import KinAccount
from kin import Keypair
from kin_base import Keypair as BaseKeypair

from . import config
from .models import Payment, Wallet, TransactionRecord
# from .utils import get_network_name
from .log import get as get_log
# from .errors import ParseError, WalletNotFoundError
from .errors import WalletNotFoundError
from .config import STELLAR_ENV

log = get_log('rq.worker')

class Blockchain(object):
    read_sdk = KinClient(STELLAR_ENV)
    minimum_fee = read_sdk.get_minimum_fee()

    def __init__(self, sdk: KinAccount, channel: str):
        self.write_sdk = sdk
        self.write_sdk.raw_seed = BaseKeypair.from_seed(sdk.keypair.secret_seed).raw_seed()
        self.root_address = self.write_sdk.keypair.public_address
        self.channel = channel
        self.channel_address = Keypair.address_from_seed(channel)

    def create_wallet(self, public_address: str) -> str:
        """create a wallet."""
        # try:
        #     account_exists = self.write_sdk.check_account_exists(public_address)
        # except Exception as e:
        #     log.info('failed checking wallet state', public_address=public_address)
        # else:
        #     if account_exists:
        #         raise AccountExistsError

        log.info('creating wallet', public_address=public_address)

        # We use 'build_create_account' instead of 'create_account' since we have our method of managing seeds in redis
        builder = self.write_sdk.build_create_account(public_address, 0, self.minimum_fee)
        tx_id = self._sign_and_send_tx(builder)
        log.info('create wallet transaction', tx_id=tx_id)
        return tx_id

    def pay_to(self, public_address: str, amount: int, payment_id: str) -> str:
        """send kins to an address."""
        log.info('sending kin to', address=public_address)
        # We use 'build_send_kin' instead of 'send_kin' since we have our method of managing seeds in redis
        builder = self.write_sdk.build_send_kin(public_address, amount, fee=self.minimum_fee, memo_text=payment_id)
        return self._sign_and_send_tx(builder)

    @staticmethod
    def get_wallet(public_address: str) -> Wallet:
        try:
            data = Blockchain.read_sdk.get_account_data(public_address)
            return Wallet.from_blockchain(data)
        except AccountNotFoundError:
            raise WalletNotFoundError('wallet %s not found' % public_address)

    @staticmethod
    def get_transaction_data(tx_id) -> SimplifiedTransaction:
        return Blockchain.read_sdk.get_transaction_data(tx_id)

    @staticmethod
    def get_payment_data(tx_id) -> Payment:
        return Payment.from_blockchain(Blockchain.get_transaction_data(tx_id))

    @staticmethod
    def try_parse_payment(tx_data) -> Payment:
        """try to parse payment from given tx_data. return None when failed."""
        try:
            return Payment.from_blockchain(tx_data)
        # except ParseError as e:  # todo Ron: Why was this removed
        #     log.exception('failed to parse payment', tx_data=tx_data)
        #     return
        except Exception as e:
            log.exception('failed to parse payment', tx_data=tx_data)

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

    def _sign_and_send_tx(self, builder) -> str:
        builder.set_channel(self.channel)
        builder.sign(self.channel)
        if self.channel != self.write_sdk.keypair.secret_seed:
            builder.sign(self.write_sdk.keypair.secret_seed)
        tx_id = self.write_sdk.submit_transaction(builder)
        return tx_id


# The wallet that funds all other channels and sub-funding-wallets
root_account = Blockchain.read_sdk.kin_account(config.STELLAR_BASE_SEED, channel_secret_keys=[], app_id='')  # We need to choose an app_id
root_wallet = Blockchain(root_account, root_account.keypair.secret_seed)


@contextlib.contextmanager
def get_sdk(seed: str, app_id: str) -> Blockchain:
    from .channel_factory import get_channel

    sdk = Blockchain.read_sdk.kin_account(seed, app_id=app_id)

    with get_channel(root_wallet) as channel:
        try:
            yield Blockchain(sdk, channel)
        finally:
            pass
