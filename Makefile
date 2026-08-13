.PHONY: reset demo warmup

export PYTHONPATH := src
PYTHON ?= $(firstword $(wildcard .venv/bin/python) python3)

reset:
	$(PYTHON) -m perpetual.demo reset

warmup:
	$(PYTHON) -m perpetual.demo warmup

demo: reset warmup
	$(PYTHON) -m perpetual.demo status
	$(PYTHON) -m perpetual.demo birth-check
