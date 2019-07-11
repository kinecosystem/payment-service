#!/bin/sh

# Usage:
# . ./test.sh  <PATH>




if [ ${DEBUG} == "True" ]; then
        ECHO "DEBUG"
        set -x
fi

# Get all SSM params from path per region
# Export key/values as environment variables
. ./config/getKeys.sh


echo "Starting: integration tests"
pipenv run py.test --cov=payment ./test.py
