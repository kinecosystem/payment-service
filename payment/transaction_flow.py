from .blockchain import kin_sdk
from .log import get as get_log


log = get_log()


class TransactionFlow():
    """class that saves the last cursor when getting transactions."""
    def __init__(self, cursor):
        self.cursor = cursor

    def _yield_transactions(self, get_records):
        """yield transactions from the given function."""
        records = get_records(self.cursor)
        while records:
            for record in records:
                if (record['type'] == 'payment'
                        and record.get('asset_code') == kin_sdk.kin_asset.code
                        and record.get('asset_issuer') == kin_sdk.kin_asset.issuer):
                    yield record
                self.cursor = record['paging_token']
            records = get_records(self.cursor)

    def get_address_transactions(self, address):
        """get KIN payment transactions for given address."""
        def get_address_records(cursor):
            log.debug('getting records from', address=address, cursor=cursor)
            reply = kin_sdk.horizon.account_payments(
                address=address,
                params={'cursor': cursor,
                        'order': 'asc',
                        'limit': 100})
            records = reply['_embedded']['records']
            log.debug('got records', num=len(records), cursor=cursor)
            return records

        for record in self._yield_transactions(get_address_records):
            yield kin_sdk.get_transaction_data(record['transaction_hash'])

    def get_transactions(self, addresses):
        """get KIN payment transactions for given addresses."""
        def get_all_records(cursor):
            log.debug('getting records from', cursor=cursor)
            reply = kin_sdk.horizon.payments(
                params={'cursor': cursor,
                        'order': 'asc',
                        'limit': 100})
            records = reply['_embedded']['records']
            log.debug('got records', num=len(records), cursor=cursor)
            return records

        for record in self._yield_transactions(get_all_records):
            if record['to'] in addresses:
                yield record['to'], kin_sdk.get_transaction_data(record['transaction_hash'])
            elif record['from'] in addresses:
                yield record['from'], kin_sdk.get_transaction_data(record['transaction_hash'])
            # else - address is not watched
