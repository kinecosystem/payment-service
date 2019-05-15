from payment.channel_factory import generate_key, Blockchain
from payment.blockchain import root_wallet
from payment.log import get as get_log
from kin import KinErrors

log = get_log()

channel_id = 0
while channel_id < 2000:
    keys = generate_key(root_wallet, channel_id)
    public_address = keys.address().decode()
    try:
        root_wallet.create_wallet(public_address)  # XXX this causes a race-condition
        log.error('# created channel: %s: %s' % (channel_id, public_address))
        channel_id += 1
    except KinErrors.AccountExistsError:
        log.error('# existing channel: %s: %s' % (channel_id, public_address))
        channel_id += 1
    except Exception as e:
        log.error('# error with channel channel: %s: %s' % (channel_id, public_address))
