all:
	trap 'kill %1' SIGINT; make run & make worker 

split: 
	tmux new-session 'make run' \; split-window 'make worker' \;

run:
	APP_REDIS=redis://localhost:6379/0 APP_PORT=5000 . ./secrets/.secrets && pipenv run python main.py

worker:
	APP_REDIS=redis://localhost:6379/0 . ./secrets/.secrets && pipenv run rq worker

shell:
	. ./secrets/.secrets && pipenv run ipython

run-prod:
	# XXX change to gunicorn
	. ./secrets/.secrets && python3 main.py

worker-prod:
	. ./secrets/.secrets && rq worker --url $$REDIS

install-prod:
	pipenv run pip freeze > requirements.txt
	pip3 install requirements.txt


# docker related
revision := $(shell git rev-parse --short HEAD)
image := "kinecosystem/payment-service"

build-image:
	docker build -t ${image} -f Dockerfile \
		--build-arg BUILD_COMMIT="${revision}" \
		--build-arg BUILD_TIMESTAMP="$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")" .
	docker tag ${image} ${image}:${revision}

push-image:
	docker push ${image}:latest
	docker push ${image}:${revision}

up:
	. ./secrets/.secrets && docker-compose up

generate-funding-address:
	docker-compose -f docker-compose.tests.yaml run generate-funding-address


.PHONY: build-image push-image up generate-funding-address shell run run-prod install-prod
