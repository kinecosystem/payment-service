run:
	. ./secrets.sh && pipenv run python main.py

shell:
	. ./secrets.sh && pipenv run ipython

run-prod:
	# XXX change to gunicorn
	. ./secrets.sh && python3 main.py

install-prod:
	pipenv run pip freeze > requirements.txt
	pip3 install requirements.txt


.PHONY: shell run run-prod install-prod
