from collections import namedtuple
from schematics import Model
from schematics.types import StringType, IntType


Memo = namedtuple('Memo', ['app_id', 'order_id'])
db = {}


class Transaction(Model):
    id = StringType()
    app_id = StringType()
    order_id = StringType()
    recipient_address = StringType()
    sender_address = StringType()
    amount = IntType()

    @classmethod
    def from_blockchain(cls, data):
        t = Transaction()
        t.id = data.operations[0].id
        t.sender_address = data.operations[0].from_address
        t.recipient_address = data.operations[0].to_address
        t.order_id = cls.parse_memo(data.memo).order_id
        t.app_id = cls.parse_memo(data.memo).app_id
        t.amount = int(data.operations[0].amount)
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
    def get(cls, id):
        for t in db.values():
            if t.id == id:
                return Transaction(t)
        raise KeyError(id)

    @classmethod
    def get_by_order_id(cls, order_id):
        return Transaction(db[order_id])

    def save(self):
        db[self.order_id] = self.to_primitive()
