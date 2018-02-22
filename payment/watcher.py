from .blockchain import kin_sdk


# define a callback function that receives an address and a kin.TransactionData object
def callback(address, tx_data):
    print(address, tx_data)


kin_sdk.monitor_kin_payments(callback)
