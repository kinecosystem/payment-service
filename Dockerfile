FROM python:3.6-alpine

RUN apk update && apk add --no-cache git build-base
RUN pip install -U pip pipenv
WORKDIR /opt/app/
COPY Pipfile* /opt/app/
RUN pipenv install 
COPY . .

ARG BUILD_COMMIT
ARG BUILD_TIMESTAMP

ENV BUILD_COMMIT $BUILD_COMMIT
ENV BUILD_TIMESTAMP $BUILD_TIMESTAMP

CMD [ "pipenv", "run", "python", "main.py" ]
