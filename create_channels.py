from payment.blockchain import kin_sdk
from kin.sdk import Keypair


if __name__ == '__main__':
    print('start')
    for i in range(4):
        keys = Keypair.random()
        public_address = keys.address().decode()
        private_seed = keys.seed().decode()

        memo = '1-kin-init_channel'
        initial_xlm_amount = 5
        tx_id = kin_sdk.create_account(public_address, initial_xlm_amount, memo)

        print(private_seed)
