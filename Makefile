.PHONY: check test

check: test
	PYTHONPATH=src python3 scripts/check_repository.py

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v
	PYTHONPATH=src python3 experiments/A0.1R-partial-block-residual/test_task0.py -v
	PYTHONPATH=src python3 experiments/A0.2-foreground-length-qualification/test_qualification.py -v
