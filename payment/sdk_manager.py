import contextlib
from .channel_factory import get_channel
from kin.errors import AccountExistsError, AccountNotFoundError
from kin.sdk import Keypair, ChannelManager, SDK
from . import config
from .utils import get_network_name
import stellar_base


def init(seed='', channels=[]):
    kin_sdk = SDK(
        secret_key=seed,
        horizon_endpoint_uri=config.STELLAR_HORIZON_URL,
        network=get_network_name(config.STELLAR_NETWORK),
        channel_secret_keys=channels,
        kin_asset=stellar_base.asset.Asset(config.STELLAR_KIN_TOKEN_NAME,
                                           config.STELLAR_KIN_ISSUER_ADDRESS))

    return kin_sdk


def read_only():
    return init() 


def seed_to_address(seed: str) -> str:
    """convert seed to address."""
    return Keypair.from_seed(seed).address().decode()


_write_sdks = {}


@contextlib.contextmanager
def write(seed):
    global _write_sdks
    address = seed_to_address(seed)

    # find if this address already was initialized
    if address not in _write_sdks:
        _write_sdks[address] = init(seed)
    sdk = _write_sdks[address]

    with get_channel(sdk) as channel:
        channels = [channel]
        sdk.channel_manager = ChannelManager(seed, channels, sdk.network, sdk.horizon)

        sdk.root_wallet_address = address
        sdk.channel_wallet_addresses = [seed_to_address(ch_seed) for ch_seed in channels]

        yield sdk

    sdk.channel_manager = None
    sdk.channel_wallet_addresses = []
