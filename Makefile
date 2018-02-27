run:
	source ./secrets.sh && pipenv run python main.py

shell:
	source ./secrets.sh && pipenv run ipython

.PHONY: shell run
