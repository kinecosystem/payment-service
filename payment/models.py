from collections import namedtuple
from datetime import datetime
from schematics import Model
from schematics.types import StringType, IntType, DateTimeType
from .errors import OrderNotFoundError


Memo = namedtuple('Memo', ['app_id', 'order_id'])
db = {}


class WalletAddress(Model):
    wallet_address = StringType()
    app_id = StringType()
    # XXX validate should raise 400 error


class Wallet(Model):
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


class Payment(Model):
    amount = IntType()
    app_id = StringType()
    order_id = StringType()
    wallet_address = StringType()


class Order(Model):
    id = StringType()
    app_id = StringType()
    transaction_id = StringType()
    recipient_address = StringType()
    sender_address = StringType()
    amount = IntType()
    timestamp = DateTimeType(default=datetime.utcnow())

    @classmethod
    def from_blockchain(cls, data):
        t = Order()
        t.id = cls.parse_memo(data.memo).order_id
        t.app_id = cls.parse_memo(data.memo).app_id
        t.transaction_id = data.operations[0].id
        t.sender_address = data.operations[0].from_address
        t.recipient_address = data.operations[0].to_address
        t.amount = int(data.operations[0].amount)
        t.timestamp = data.created_at
        return t

    @classmethod
    def parse_memo(cls, memo):
        version, app_id, order_id = memo.split('-')
        return Memo(app_id, order_id)

    @classmethod
    def create_memo(cls, app_id, order_id):
        """serialize args to the memo string."""
        return '1-{}-{}'.format(app_id, order_id)
   
    @classmethod
    def get_by_transaction_id(cls, tx_id):
        for t in db.values():
            if t.transaction_id == tx_id:
                return Order(t)
        raise KeyError(tx_id)

    @classmethod
    def get(cls, order_id):
        try:
            return Order(db[order_id])
        except KeyError:
            raise OrderNotFoundError(order_id)

    def save(self):
        db[self.id] = self.to_primitive()
