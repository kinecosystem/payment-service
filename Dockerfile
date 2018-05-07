FROM python:3.6-alpine

# install build tools and pipenv
RUN apk update && apk add --no-cache git build-base
RUN pip install -U pip pipenv

# copy and install pipfile (requirements)
WORKDIR /opt/app
COPY Pipfile* ./
RUN pipenv install 

# copy the code
COPY . .

# set build meta data
ARG BUILD_COMMIT
ARG BUILD_TIMESTAMP

ENV BUILD_COMMIT $BUILD_COMMIT
ENV BUILD_TIMESTAMP $BUILD_TIMESTAMP

# run the api server
CMD [ "pipenv", "run", "python", "main.py" ]
