import kin
import sys


def trust_kin(private_seed: str):
    sdk = kin.SDK(network='TESTNET', base_seed=private_seed)
    sdk._trust_asset(sdk.kin_asset)


if __name__ == '__main__':
    private_seed = sys.argv[1]
    trust_kin(private_seed)
