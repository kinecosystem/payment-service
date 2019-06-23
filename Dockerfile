FROM python:3.7-alpine3.8

WORKDIR /opt/app

# copy pipfile (requirements)
COPY Pipfile* ./

# install build tools and pipenv

RUN apk update && apk add -qU --no-cache -t .fetch-deps git build-base
RUN apk add jq bash curl\
    && pip install -U pip pipenv \
    && pipenv install -d \
    && apk del -q .fetch-deps

RUN  pip install awscli --upgrade

## Install aws-cli, used for SSM params
#RUN apk -Uuv add groff less python py-pip jq curl
#RUN pip install awscli
#RUN apk --purge -v del py-pip
#RUN rm /var/cache/apk/*


# copy the code
COPY . .

# set build meta data
ARG BUILD_COMMIT
ARG BUILD_TIMESTAMP

ENV BUILD_COMMIT $BUILD_COMMIT
ENV BUILD_TIMESTAMP $BUILD_TIMESTAMP

RUN chmod 775 ./config/*.sh
#get ssm paramaeter as environment variable
# run the api server
#For backward compatibility, overriden by the k8s deployment yaml
#CMD ["/bin/sh", "-c",   "./config/startup.sh" ]

# run the api server
#ENTRYPOINT ["/bin/sh", "-c",   "./config/startup.sh"]
CMD pipenv run gunicorn -b $APP_HOST:$APP_PORT payment.app:app
