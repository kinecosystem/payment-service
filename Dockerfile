FROM python:3.7-alpine3.8

WORKDIR /opt/app

# copy pipfile (requirements)
COPY Pipfile* ./

# install build tools and pipenv
RUN apk add -qU --no-cache -t .fetch-deps git build-base \
    && pip install -U pip pipenv \
    && pipenv install \
    && apk del -q .fetch-deps

# copy the code
COPY . .

# set build meta data
ARG BUILD_COMMIT
ARG BUILD_TIMESTAMP

ENV BUILD_COMMIT $BUILD_COMMIT
ENV BUILD_TIMESTAMP $BUILD_TIMESTAMP

# run the api server
CMD pipenv run gunicorn -b $APP_HOST:$APP_PORT payment.app:app
