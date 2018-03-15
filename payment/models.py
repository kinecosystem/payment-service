import json
from collections import namedtuple
from datetime import datetime
from schematics import Model
from schematics.types import StringType, IntType, DateTimeType, ListType
from .errors import PaymentNotFoundError


Memo = namedtuple('Memo', ['app_id', 'payment_id'])
db = {}
watcher_db = {}


class ModelWithStr(Model):
    def __str__(self):
        return json.dumps(self.to_primitive())

    def __repr__(self):
        return str(self)


class WalletRequest(ModelWithStr):
    wallet_address = StringType()
    app_id = StringType()
    # XXX validate should raise 400 error


class Wallet(ModelWithStr):
    wallet_address = StringType()
    kin_balance = IntType()
    native_balance = IntType()

    @classmethod
    def from_blockchain(cls, data, kin_asset):
        wallet = Wallet()
        wallet.wallet_address = data.id
        wallet.kin_balance = int(next(
            (coin.balance for coin in data.balances
             if coin.asset_code == kin_asset.code
             and coin.asset_issuer == kin_asset.issuer), 0))
        wallet.native_balance = int(next(
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
    id = StringType()
    app_id = StringType()
    transaction_id = StringType()
    recipient_address = StringType()
    sender_address = StringType()
    amount = IntType()
    timestamp = DateTimeType(default=datetime.utcnow())

    @classmethod
    def from_blockchain(cls, data):
        t = Payment()
        t.id = cls.parse_memo(data.memo).payment_id
        t.app_id = cls.parse_memo(data.memo).app_id
        t.transaction_id = data.operations[0].id
        t.sender_address = data.operations[0].from_address
        t.recipient_address = data.operations[0].to_address
        t.amount = int(data.operations[0].amount)
        t.timestamp = data.created_at
        return t

    @classmethod
    def parse_memo(cls, memo):
        version, app_id, payment_id = memo.split('-')
        return Memo(app_id, payment_id)

    @classmethod
    def create_memo(cls, app_id, payment_id):
        """serialize args to the memo string."""
        return '1-{}-{}'.format(app_id, payment_id)

    @classmethod
    def get_by_transaction_id(cls, tx_id):
        for t in db.values():
            if t.transaction_id == tx_id:
                return Payment(t)
        raise PaymentNotFoundError('payment with transaction {} not found'.format(tx_id))

    @classmethod
    def get(cls, payment_id):
        try:
            return Payment(db[payment_id])
        except KeyError:
            raise PaymentNotFoundError('payment {} not found'.format(payment_id))

    def save(self):
        db[self.id] = self.to_primitive()


class Watcher(ModelWithStr):
    wallet_addresses = ListType(StringType)
    callback = StringType()  # a webhook to call when a payment is complete
    service_id = StringType()

    def save(self):
        watcher_db[self.service_id] = self

    @classmethod
    def get_all(cls):
        return watcher_db.values()


# for testing:
watcher_db['kik'] = Watcher({
    'wallet_addresses': ['GC3VEVNMPOIFIQOKUYFROWR6LWQQM57OQSWLLD6TGDIPOA5S6UXQWHVL'],
    'callback': 'http://localhost:3000/v1/internal/payments',
    'service_id': 'kik',
})
