import json
from collections import namedtuple
from datetime import datetime
from schematics import Model
from schematics.types import StringType, IntType, DateTimeType, ListType
from kin.stellar.horizon_models import TransactionData
from .errors import PaymentNotFoundError, ParseError
from .redis_conn import redis_conn
from redis import WatchError


Memo = namedtuple('Memo', ['app_id', 'payment_id'])


class ModelWithStr(Model):
    def __str__(self):
        return json.dumps(self.to_primitive())

    def __repr__(self):
        return str(self)


class WalletRequest(ModelWithStr):
    wallet_address = StringType()
    app_id = StringType()
    id = StringType()
    callback = StringType()  # a webhook to call when a wallet creation is complete
    # XXX validate should raise 400 error


class Wallet(ModelWithStr):
    wallet_address = StringType()
    kin_balance = IntType()
    native_balance = IntType()
    id = StringType()

    @classmethod
    def from_blockchain(cls, data, kin_asset):
        wallet = Wallet()
        wallet.wallet_address = data.id
        kin_balance = next(
            (coin.balance for coin in data.balances
             if coin.asset_code == kin_asset.code
             and coin.asset_issuer == kin_asset.issuer), None)
        wallet.kin_balance = None if kin_balance is None else int(kin_balance)
        wallet.native_balance = float(next(
            (coin.balance for coin in data.balances
             if coin.asset_type == 'native'), 0))
        return wallet


class PaymentRequest(ModelWithStr):
    amount = IntType()
    app_id = StringType()
    recipient_address = StringType()
    id = StringType()
    callback = StringType()  # a webhook to call when a payment is complete


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
    def from_payment_request(cls, request: PaymentRequest, sender_address: str, tx_id: str):
        p = Payment()
        p.id = request.id
        p.app_id = request.app_id
        p.transaction_id = tx_id
        p.sender_address = sender_address
        p.recipient_address = request.recipient_address
        p.amount = request.amount
        return p

    @classmethod
    def from_blockchain(cls, data: TransactionData):
        p = Payment()
        p.id = cls.parse_memo(data.memo).payment_id
        p.app_id = cls.parse_memo(data.memo).app_id
        p.transaction_id = data.hash
        # p.operation_id = data.operations[0].id
        p.sender_address = data.operations[0].from_address
        p.recipient_address = data.operations[0].to_address
        p.amount = int(data.operations[0].amount)
        p.timestamp = data.created_at
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
    callback = StringType()  # a webhook to call when a payment is complete
    service_id = StringType()

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
        return redis.conn.smembers(cls._all_services_key())  # XXX what type returns?

    def save(self):
        redis_conn.set(self._key(self.service_id), json.dumps(self.to_primitive()))
        redis_conn.sadd(self._all_services_key(), self.service_id)

    def delete(self):
        redis_conn.delete(self._key(self.service_id))
        redis_conn.srem(self._all_services_key(), self.service_id)

    def _service_addresses_key(self):
        return 'service:%s:addresses' % self.service_id)

    def _service_address_key(self, address):
        return 'service:%s:address:%s' % (self.service_id, address)

    @retry(5, delay=0) # XXX retry on redis.WatchError
    def add_watcher(self, address, payment_id):
        with redis_conn.pipeline(transaction=False) as pipe:
            pipe.watch(self._service_addresses_key())
            pipe.multi()
            pipe.sadd(self._service_address_key(address), payment_id)
            pipe.sadd(self._service_addresses_key(), address)
            pipe.execute()

    def delete_watcher(self, address, payment_id):
        with redis_conn.pipeline(transaction=False) as pipe:
            pipe.watch(self._service_addresses_key())
            pipe.srem(self._service_address_key(address), payment_id)
            if pipe.smembers(self._service_address_key(address)) == 0:
                pipe.multi()
                pipe.srem(self._service_addresses_key(), address)
            pipe.execute()


class Watcher(ModelWithStr):
    wallet_addresses = ListType(StringType)
    callback = StringType()  # a webhook to call when a payment is complete
    service_id = StringType()

    def save(self):
        redis_conn.hset(self._key(), self.service_id, json.dumps(self.to_primitive()))

    def add_addresses(self, addresses):
        self.wallet_addresses = list(
            set(self.wallet_addresses) | set(addresses))

    @classmethod
    def get(cls, service_id):
        data = redis_conn.hget(cls._key(), service_id)
        if not data:
            return None
        return Watcher(json.loads(data.decode('utf8')))

    @classmethod
    def _key(cls):
        return 'watchers:2'

    @classmethod
    def get_all(cls):
        data = redis_conn.hgetall(cls._key()).values()

        return [Watcher(json.loads(w.decode('utf8'))) for w in data]

    @classmethod
    def get_subscribed(cls, address):
        """get only watchers who are interested in this address."""
        return [w for w in cls.get_all()
                if address in w.wallet_addresses]


class TransactionRecord(ModelWithStr):
    to_address = StringType(serialized_name='to', required=True)
    from_address = StringType(serialized_name='from', required=True)
    transaction_hash = StringType(required=True)
    asset_code = StringType()
    asset_issuer = StringType()
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

