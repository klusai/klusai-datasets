.PHONY: help test lint check install

VENV := .venv/bin/activate
RUN := source $(VENV) &&

help:
	@echo "  make install  - editable install + dev deps into .venv"
	@echo "  make test     - run tests with coverage"
	@echo "  make lint     - run ruff"
	@echo "  make check    - test + lint"

install:
	# Install self (pulls europriv-bench from GitHub), then override with the sibling editable
	# so local changes to the shared taxonomy/spans are picked up during development.
	$(RUN) pip install -e '.[dev]'
	$(RUN) pip install -e ../europriv-bench

test:
	$(RUN) coverage run -m pytest
	$(RUN) coverage report

lint:
	$(RUN) ruff check .

check: test lint
