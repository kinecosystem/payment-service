from payment.channel_factory import get_next_channel_id, generate_key
from payment.blockchain import root_wallet
import time


def main3():
    for i in range(20):
        print(i, generate_key(root_wallet, i).address())


def main2():
    with get_next_channel_id() as ch0:
        print(ch0)
        with get_next_channel_id() as ch1:
            print(ch1)
            with get_next_channel_id() as ch2:
                print(ch2)
                time.sleep(0.5)


def main1():
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

    with get_sdk(config.STELLAR_BASE_SEED) as bc1:
        print(bc1.channel_addresses[0])
        print('wallet: ', Blockchain.get_wallet(bc1.channel_addresses[0]))


if __name__ == '__main__':
    main1()
