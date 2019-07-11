#!/bin/sh
# Usage:
# . ./config/startup.sh

echo "Role: ${ROLE}"
if [[ "True" == "${DEBUG}"  ]]; then
        ECHO "DEBUG"
        set -x
fi

# Get all SSM params from path per region
# Export key/values as environment variables
. ./config/getKeys.sh


echo "Starting: payment-service ${ROLE}"

if  [[ "watcher" == "${ROLE}" ]]; then
    sh -c "pipenv run python watcher.py"
elif  [[ "worker" == "${ROLE}" ]]; then
    sh -c "pipenv run python worker.py"
elif  [[ "web" == "${ROLE}" ]]; then
    pipenv run gunicorn -b $APP_HOST:$APP_PORT payment.app:app
else
    echo "No Role Specified...Exiting"
    exit 1
fi




