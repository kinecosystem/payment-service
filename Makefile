all:
	trap 'kill %1' SIGINT; make run & make worker 

up:
	. ./secrets.sh && docker-compose up

split: 
	tmux new-session 'make run' \; split-window 'make worker' \;

run:
	APP_PORT=5000 . ./secrets.sh && pipenv run python main.py

worker:
	. ./secrets.sh && pipenv run rq worker

shell:
	. ./secrets.sh && pipenv run ipython

run-prod:
	# XXX change to gunicorn
	. ./secrets.sh && python3 main.py

worker-prod:
	. ./secrets.sh && rq worker --url $$REDIS

install-prod:
	pipenv run pip freeze > requirements.txt
	pip3 install requirements.txt


.PHONY: shell run run-prod install-prod

revision := $(shell git rev-parse --short HEAD)
image := "kinecosystem/payment-service"

build:
	docker build -t ${image} -f Dockerfile \
		--build-arg BUILD_COMMIT="${revision}" \
		--build-arg BUILD_TIMESTAMP="$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")" .
	docker tag ${image} ${image}:${revision}

push:
	docker push ${image}:latest
	docker push ${image}:${revision}
