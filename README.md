# Kin Ecosystem Payment Service

The payment-service is a service meant to be run internally, i.e. not directly connected to the internet. It provides the functionality to:
* send KIN payments
* subscribe on KIN payments sent/received on any given address
* fund new stellar wallets

<a href="https://partners.kinecosystem.com/docs/server_payment_service.html"><img src="https://partners.kinecosystem.com/img/documentation-button2x.png" width=300 height=84 alt="Documentation"/></a>

The service is initiated with a root wallet account that contains sufficient KIN and XLM. The service is diveded into 3:
1. Http server for incoming requests
1. Background worker to process payment requests and perform callbacks
1. Polling process that listens on the blockchain and sends callbacks on any transaction involving a presubscribed address

The server implements a global lock over payment ids, to prevent double spend in case of race-conditions. The server - worker communication is implemented over redis, using the [rq](http://python-rq.org/) library.

## Setup
The service expects configuration given via configuration variables:

* `APP_REDIS` redis url ('redis://localhost:6379/0')
* `APP_PORT` web app port (5000)
* `STELLAR_HORIZON_URL` horizon url ('https://horizon-kik.kininfrastructure.com')
* `STELLAR_NETWORK` stellar network name or passpharse ('PUBLIC'/'TESTNET'/'private testnet')
* `STELLAR_KIN_ISSUER_ADDRESS` stellar asset issuer ('GBQ3DQOA7NF52FVV7ES3CR3ZMHUEY4LTHDAQKDTO6S546JCLFPEQGCPK')
* `STELLAR_KIN_TOKEN_NAME` stellar asset name ('KIN')
* `KIN_FAUCET` url of a KIN faucet ('http://159.65.84.173:5000') - used for `generate-funding-address` makefile target
* `XLM_FAUCET` url of a XLM faucet/ friendbot ('http://friendbot-kik.kininfrastructure.com')
* `STELLAR_INITIAL_XLM_AMOUNT` initial amount of XLM when funding a wallet (2)

An example for these variables exists in `local.sh`. The makefile uses this file to export the variables and run the services.

In addition to the public configuration, there is a "secret" configuration which contains the stellar private keys for the root wallet of the service (this is the wallet that will create accounts and send KIN):
* `STELLAR_BASE_SEED` Main stellar secret key

They can either be generated using the `make generate-funding-address` script or manually created. Make sure the address contains enough KIN and XLM for operation.

For the worker, you need to configure a `CHANNEL_SALT` that will be used to derive a channel to sign outgoing transactions and enable concurrency across multiple workers.

## Flow

The payment-service is intended to run in an internal network detached from the internet. A user facing web app receives internet traffic and decides to pay a user.

### Pay
`POST /payments` - see swagger for details

The endpoint receives the information for the payment including an id, amount, recipient wallet and completion_callback, and creates a background task to pay the given wallet:
```python
class PaymentRequest(ModelWithStr):
    amount = IntType()
    app_id = StringType()
    recipient_address = StringType()
    id = StringType()
    callback = StringType()  # a webhook to call when a payment is complete
```
The blockchain transaction will include the `app_id` and `id` of the payment in the memo field.

Once the payment is done, the payment-server notifies the completion_callback using an **`HTTP POST`** method including the payment information:
```python
class Payment(ModelWithStr):
    id = StringType()
    app_id = StringType()
    transaction_id = StringType()
    recipient_address = StringType()
    sender_address = StringType()
    amount = IntType()
    timestamp = DateTimeType(default=datetime.utcnow())
```

------

Say the user facing server decides to create a new wallet:
### Create Wallet
`POST /wallets`

The payload is
```
class WalletRequest(ModelWithStr):
    wallet_address = StringType()
    app_id = StringType()
```
The app_id will be written to the blockchain transaction and wallet will be create (no notification/ callback).

------

When the user facing server, presents a spend offer, it can subscribe to updates on KIN payments to/from a specific address, by registering a callback

### Watch
`PUT/ DELETE /services/<service_id>`
```python
class Service(ModelWithStr):
    callback = StringType()  # a webhook to call when a payment is complete
    service_id = StringType()
    wallet_addresses = ListType(StringType)  # permanent addresses
```

A few different services can register callbacks. Each service is identified by `service_id`.

To register to a specific payment on a specific address:
`PUT/ DELETE /services/<service_id>/watchers/<address>/payments/<payment_id>`

When the payment-service encounters a KIN payment including a registered wallet_address in either the `to` or `from` fields, it calls all the subscribed services' callback using the `HTTP POST` method with the payment payload (same as **Pay** command):
```python
class Payment(ModelWithStr):
    id = StringType()
    app_id = StringType()
    transaction_id = StringType()
    recipient_address = StringType()
    sender_address = StringType()
    amount = IntType()
    timestamp = DateTimeType(default=datetime.utcnow())
```

------

In addition there are `HTTP GET` endpoints for getting information on a specific wallet balance or transactions, or getting information on a specific payment.
The server has a healthcheck endpoint `/status` and a configuration endpoint `/config` that shows the blockchain configuration that the service is running with.


## API
http://editor.swagger.io/?url=https://raw.githubusercontent.com/kinfoundation/ecosystem-api/master/payment.yaml

## Development

### Setting up a local development environment

*This procedure is a work-in-progress and as of now is targeting MacOS machines, sorry others*


#### Step 1: Clone this Repo

#### Step 2: Install dependencies
Change into the Repo's directory and run ```pipenv install``` (Python 3 and pipenv are prerequisites)

#### Step 3: Install and setup Redis

###### Install Redis
```brew install redis```

###### Create a link to launch Redis on startup:
 ```ln -sfv /usr/local/opt/redis/*.plist ~/Library/LaunchAgents```

###### Use launchctl to launch redis:
```launchctl load ~/Library/LaunchAgents/homebrew.mxcl.redis.plist```

#### Step 4: create or set the secrets file with wallet data
You need to have a stellar account with funds and create a `secrets/.secrets` file locally with the following content:
```
export STELLAR_BASE_SEED=SXXX
```

#### Step 5: Run the service (hopefully)
Run ```make``` which will run 3 processes:
* payment-service web
* worker
* watcher

## Running in Docker
To run and test using docker follow the instructions bellow:

#### Setup
*Download docker + docker-compose for your environment.*

If you **DON'T** have a wallet with XLM and KIN:
Run the following command to generate a `secrets/.secrets` file with a pre-funded wallet:
```
make generate-funding-address
```
Note that this command will overwrite any existing file `secrets/.secrets`.

If you have a wallet with XLM and KIN:
You need to have a stellar account with funds and create a `secrets/.secrets` file locally with the following content:
```
export STELLAR_BASE_SEED=SXXX
```

#### Run docker servers and system tests
Run the following command:
```
make up  # start all services
```
