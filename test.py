import pytest
import time
from payment.app import app
from payment import config; config.MAX_CHANNELS = 3

from payment.channel_factory import get_next_channel_id, generate_key
from payment.blockchain import root_wallet
from payment.redis_conn import redis_conn
from payment.utils import lock, safe_int
from payment.models import Payment, Service


def test_lock():
    try:
        with lock(redis_conn, 'test:{}'.format(3), blocking_timeout=120):
            print('lock1')
            time.sleep(3)
            with lock(redis_conn, 'test:{}'.format(4), blocking_timeout=120):
                print('lock2')
                raise Exception
    except:
        print('caught')
    else:
        assert False, 'should throw'


def test_generate_keys():
    keys1 = [generate_key(root_wallet, i).address() for i in range(20)]
    keys2 = [generate_key(root_wallet, i).address() for i in range(20)]

    assert keys1 == keys2


def test_channel_rotate():
    with get_next_channel_id() as ch0:
        print(ch0)
        with get_next_channel_id() as ch1:
            print(ch1)
            with get_next_channel_id() as ch2:
                print(ch2)
                time.sleep(0.5)
                assert ch1 != ch2 != ch0


def test_generate_channels():
    from payment.blockchain import Blockchain, get_sdk
    from payment import config
    print('started')
    cursor = Blockchain.get_last_cursor()
    records = Blockchain.get_all_records(cursor, 100)
    if not records:
        print('no records')
    else:
        print('wallet: ', Blockchain.get_wallet(records[0].from_address))

    with get_sdk(config.STELLAR_BASE_SEED) as bc1:
        print(bc1.channel_addresses[0])
        print('wallet: ', Blockchain.get_wallet(bc1.channel_addresses[0]))
        with get_sdk(config.STELLAR_BASE_SEED) as bc2:
            print(bc2.channel_addresses[0])
            print('wallet: ', Blockchain.get_wallet(bc2.channel_addresses[0]))
            with get_sdk(config.STELLAR_BASE_SEED) as bc3:
                print(bc3.channel_addresses[0])
                print('wallet: ', Blockchain.get_wallet(bc3.channel_addresses[0]))
                assert bc1.channel_addresses != bc2.channel_addresses != bc3.channel_addresses
        orig_bc1_channel_addresses = bc1.channel_addresses

    with get_sdk(config.STELLAR_BASE_SEED) as bc1:
        print(bc1.channel_addresses[0])
        print('wallet: ', Blockchain.get_wallet(bc1.channel_addresses[0]))
        # assert only true if MAX_CHANNELS == 3
        assert bc1.channel_addresses in (orig_bc1_channel_addresses, bc2.channel_addresses, bc3.channel_addresses)


def test_load_from_redis():
    p = Payment({'id': 'test',
                 'app_id': 'test',
                 'transaction_id': 'test',
                 'recipient_address': 'test',
                 'sender_address': 'test',
                 'amount': 1})
    Payment(p.to_primitive())
    p.save()
    Payment.get('test')


def test_status(client):
    res = client.get('/status')
    assert res.json['app_name'] == 'payment-service'


def test_watching():
    service = Service({
        'service_id': 'my_service',
        'callback': 'my_callback',
        'wallet_addresses': [],
    })
    service.save()

    service.watch_payment('address-1', 'pay-1')
    service.watch_payment('address-1', 'pay-2')
    service.watch_payment('address-1', 'pay-3')
    assert Service.get_all_watching_addresses() == {'address-1'}
    service.watch_payment('address-2', 'pay-4')
    assert Service.get_all_watching_addresses() == {'address-1', 'address-2'}
    service.unwatch_payment('address-1', 'pay-3')
    service.unwatch_payment('address-2', 'pay-4')
    assert Service.get_all_watching_addresses() == {'address-1'}
    service.unwatch_payment('address-1', 'pay-2')
    service.unwatch_payment('address-1', 'pay-1')
    assert Service.get_all_watching_addresses() == set()
    service.delete()


def test_safe_int():
    assert 1 == safe_int('blah', 1)
    assert 2 == safe_int(2, 1)
    assert 2 == safe_int('2', 1)


def test_old_new_watchers(client):
    client.put('/watchers/my_service', json={'callback': 'my_callback', 'wallet_addresses': ['old-1', 'old-2']})
    client.put('/services/my_service', json={'callback': 'my_callback', 'wallet_addresses': ['old-1', 'old-2']})
    client.put('/services/my_service/watchers/address-1/payments/pay-1')
    client.put('/services/my_service/watchers/address-1/payments/pay-2')
    client.put('/services/my_service/watchers/address-2/payments/pay-3')

    res = client.get('/watchers')
    raise Exception(res.json)



@pytest.fixture
def client():
    app.config['TESTING'] = True
    client = app.test_client()

    yield client
