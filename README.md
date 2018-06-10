# Kin Ecosystem Payment Service

The payment-service is a service meant to be run internally, i.e. not directly connected to the internet. It provides the functionality to:
* send KIN payments
* subscribe on KIN payments sent/received on any given address
* fund new stellar wallets

The service is initiated with a root wallet account that contains sufficient KIN and XLM. The service is diveded into 3:
1. Http server for incoming requests
1. Background worker to process payment requests and perform callbacks
1. Polling process that listens on the blockchain and sends callbacks on any transaction involving a presubscribed address

The server implements a global lock over payment ids, to prevent double spend in case of race-conditions. The server - worker communication is implemented over redis, using the [rq](http://python-rq.org/) library.

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
export STELLAR_CHANNEL_SEEDS=SXXX
export STELLAR_BASE_SEED=SXXX
export STELLAR_ADDRESS=GXXX
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
export STELLAR_CHANNEL_SEEDS=SXXX
export STELLAR_BASE_SEED=SXXX
export STELLAR_ADDRESS=GXXX
```

#### Run docker servers and system tests
Run the following command:
```
make up  # start all services
```
