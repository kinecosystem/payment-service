from payment import blockchain
import sys


if __name__ == '__main__':
    blockchain.pay_to(sys.argv[1], 10000, 'kik', 'init')
