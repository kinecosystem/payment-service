import json
from typing import Union, List, Dict
from collections import namedtuple
from datetime import datetime
from schematics import Model
from schematics.types import StringType, IntType, DateTimeType, ListType
from kin.transactions import NATIVE_ASSET_TYPE, SimplifiedTransaction
from kin import decode_transaction
from kin import KinErrors

from .errors import PaymentNotFoundError, ParseError, TransactionMismatch

from .redis_conn import redis_conn
from .log import get as get_logger

log = get_logger()
Memo = namedtuple('Memo', ['app_id', 'payment_id'])
ADDRESS_EXP_SECS = 60 * 60  # one hour


class ModelWithStr(Model):
    def __str__(self):
        return json.dumps(self.to_primitive())

    def __repr__(self):
        return str(self)


class WalletRequest(ModelWithStr):
    wallet_address = StringType(required=True)
    app_id = StringType(required=True)
    id = StringType(required=True)
    callback = StringType(required=True)  # a webhook to call when a wallet creation is complete
    # XXX validate should raise 400 error


class Wallet(ModelWithStr):
    wallet_address = StringType()
    kin_balance = IntType()
    native_balance = IntType()
    id = StringType()

    @classmethod
    def from_blockchain(cls, data):
        wallet = Wallet()
        wallet.wallet_address = data.id
        kin_balance = next(
            (coin.balance for coin in data.balances
             if coin.asset_type == NATIVE_ASSET_TYPE))
        wallet.kin_balance = None if kin_balance is None else int(kin_balance)
        return wallet


class PaymentRequest(ModelWithStr):
    amount = IntType(required=True)
    app_id = StringType(required=True)
    recipient_address = StringType(required=True)
    id = StringType(required=True)
    callback = StringType(required=True)  # a webhook to call when a payment is complete


class WhitelistRequest(ModelWithStr):
    id = StringType(required=True)  # AKA order id
    sender_address = StringType(required=True)
    recipient_address = StringType(required=True)
    amount = IntType(required=True)
    transaction = StringType(required=True)
    app_id = StringType(required=True)
    network_id = StringType()

    @staticmethod
    def _compare_attr(attr1, attr2, attr_name):
        if attr1 != attr2:
            raise TransactionMismatch('{attr_name}: {attr1} does not match expected {attr_name}: {attr2}'.
                                      format(attr_name=attr_name,
                                             attr1=attr1,
                                             attr2=attr2))

    def verify_transaction(self):
        """Verify that the encoded transaction matches our expectations"""
        try:
            decoded_tx = decode_transaction(self.transaction, self.network_id)
        except Exception as e:
            if isinstance(e, KinErrors.CantSimplifyError):
                raise TransactionMismatch('Unexpected transaction')
            log.error('Couldn\'t decode tx with transaction xdr: {}'.format(self.transaction))
            raise TransactionMismatch('Transaction could not be decoded')
        if decoded_tx.memo is None:
            raise TransactionMismatch('Unexpected memo: Empty')
        memo_parts = decoded_tx.memo.split('-')
        if len(memo_parts) != 3:
            raise TransactionMismatch('Unexpected memo: expected a 3 part memo')
        self._compare_attr(memo_parts[1], self.app_id, 'App id')
        self._compare_attr(memo_parts[2], self.id, 'id')
        self._compare_attr(decoded_tx.source, self.sender_address, 'Sender account')
        self._compare_attr(decoded_tx.operation.destination, self.recipient_address, 'Destination account')
        self._compare_attr(decoded_tx.operation.amount, self.amount, 'Amount')
        return decoded_tx

    def whitelist(self) -> str:
        """Sign and return a transaction to whitelist it"""
        from .blockchain import root_account
        return root_account.whitelist_transaction({'envelope': self.transaction,
                                                  'network_id': self.network_id})


class SubmitTransactionRequest(WhitelistRequest):
    callback = StringType(required=True)


class Payment(ModelWithStr):
    PAY_STORE_TIME = 500
    id = StringType()
    app_id = StringType()
    transaction_id = StringType()
    recipient_address = StringType()
    sender_address = StringType()
    amount = IntType()
    timestamp = DateTimeType(default=datetime.utcnow())

    @classmethod
    def from_payment_request(cls, request: Union[PaymentRequest, SubmitTransactionRequest], sender_address: str, tx_id: str):
        p = Payment()
        p.id = request.id
        p.app_id = request.app_id
        p.transaction_id = tx_id
        p.sender_address = sender_address
        p.recipient_address = request.recipient_address
        p.amount = request.amount
        return p

    @classmethod
    def from_blockchain(cls, data: SimplifiedTransaction):
        p = Payment()
        p.id = cls.parse_memo(data.memo).payment_id
        p.app_id = cls.parse_memo(data.memo).app_id
        p.transaction_id = data.id
        p.sender_address = data.source
        p.recipient_address = data.operation.destination
        p.amount = int(data.operation.amount)
        p.timestamp = datetime.strptime(data.timestamp, '%Y-%m-%dT%H:%M:%SZ')  # 2018-11-12T06:45:40Z
        return p

    @classmethod
    def parse_memo(cls, memo):
        try:
            version, app_id, payment_id = memo.split('-')
            return Memo(app_id, payment_id)
        except Exception:
            raise ParseError

    @classmethod
    def create_memo(cls, app_id, payment_id):
        """serialize args to the memo string."""
        return '1-{}-{}'.format(app_id, payment_id)

    @classmethod
    def get(cls, payment_id):
        data = redis_conn.get(cls._key(payment_id))
        if not data:
            raise PaymentNotFoundError('payment {} not found'.format(payment_id))
        return Payment(json.loads(data.decode('utf8')))

    @classmethod
    def _key(cls, id):
        return 'payment:{}'.format(id)

    def save(self):
        redis_conn.set(self._key(self.id),
                       json.dumps(self.to_primitive()),
                       ex=self.PAY_STORE_TIME)


class Service(ModelWithStr):
    callback = StringType(required=True)  # a webhook to call when a payment is complete
    service_id = StringType(required=True)
    wallet_addresses = ListType(StringType, required=True)  # permanent addresses

    @classmethod
    def _key(cls, service_id):
        return 'service:%s' % service_id

    @classmethod
    def _all_services_key(cls):
        return 'all_services'

    @classmethod
    def get(cls, service_id):
        data = redis_conn.get(cls._key(service_id))
        if not data:
            return None
        return cls(json.loads(data.decode('utf8')))

    @classmethod
    def get_all(cls):
        return [cls.get(service_id.decode('utf8'))
                for service_id
                in redis_conn.smembers(cls._all_services_key())]  # XXX what type returns?

    def _get_all_temp_watching_addresses(self):
        def address_from_key(key):
            try:
                return key.decode('utf8').rsplit(':', 1)[-1]
            except:
                log.exception('failed address_from_key %s' % key)

        # first get the time limited addresses
        return set(address_from_key(key)
                   for key
                   in redis_conn.keys('service:%s:address:*' % self.service_id))

    def _get_all_watching_addresses(self):
        """return set of all watching addresses."""
        return self._get_all_temp_watching_addresses() | set(self.wallet_addresses)

    @classmethod
    def get_all_watching_addresses(cls) -> Dict[str, List["Service"]]:
        """get all addresses watched by any service as map of address to list of services watching it."""
        addresses = {}
        for service in cls.get_all():
            service_addresses = service._get_all_watching_addresses()
            for address in service_addresses:
                if address not in addresses:
                    addresses[address] = []
                addresses[address].append(service)

        return addresses

    def save(self):
        redis_conn.set(self._key(self.service_id), json.dumps(self.to_primitive()))
        redis_conn.sadd(self._all_services_key(), self.service_id)

    def delete(self):
        redis_conn.delete(self._key(self.service_id))
        redis_conn.srem(self._all_services_key(), self.service_id)

    def _address_payments_key(self, address):
        return 'service:%s:address:%s' % (self.service_id, address)

    def watch_payment(self, address, payment_id):
        """start looking for payment_id on given address."""
        # ignoring payment_id
        key = self._address_payments_key(address)
        redis_conn.set(key, address, ADDRESS_EXP_SECS)

    def unwatch_payment(self, address, payment_id):
        # ignoring payment_id
        return


class TransactionRecord(ModelWithStr):
    to_address = StringType(serialized_name='to', required=True)
    from_address = StringType(serialized_name='from', required=True)
    transaction_hash = StringType(required=True)
    asset_type = StringType()
    paging_token = StringType(required=True)
    type = StringType(required=True)


class CursorManager:
    @classmethod
    def save(cls, cursor):
        redis_conn.set(cls._key(), cursor)
        return cursor

    @classmethod
    def get(cls):
        cursor = redis_conn.get(cls._key())
        return cursor.decode('utf8') if cursor else None

    @classmethod
    def _key(cls):
        return 'cursor'
