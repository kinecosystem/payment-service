from payment.utils import get_network_name
import stellar_base
import os
import kin
import sys


class config:
    STELLAR_HORIZON_URL = os.environ['STELLAR_HORIZON_URL']
    STELLAR_NETWORK = os.environ['STELLAR_NETWORK']
    STELLAR_KIN_ISSUER_ADDRESS = os.environ['STELLAR_KIN_ISSUER_ADDRESS']
    STELLAR_KIN_TOKEN_NAME = os.environ['STELLAR_KIN_TOKEN_NAME']


def trust_kin(private_seed):
    kin_sdk = kin.SDK(
        secret_key=private_seed,
        horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
        network=get_network_name(config.STELLAR_NETWORK),
        kin_asset=kin.Asset.native())
    kin_asset = stellar_base.asset.Asset(config.STELLAR_KIN_TOKEN_NAME, config.STELLAR_KIN_ISSUER_ADDRESS)
    kin_sdk._trust_asset(kin_asset)


if __name__ == '__main__':
    private_seed = sys.argv[1]
    trust_kin(private_seed)
