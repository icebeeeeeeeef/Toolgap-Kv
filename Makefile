.PHONY: check test

check: test
	PYTHONPATH=src python3 scripts/check_repository.py

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v
