import kin
import sys


def trust_kin(private_seed: str):
    sdk = kin.SDK(network='TESTNET', secret_key=private_seed, kin_asset=kin.Asset.native())
    sdk._trust_asset(kin.KIN_ASSET_TEST)


if __name__ == '__main__':
    private_seed = sys.argv[1]
    trust_kin(private_seed)
