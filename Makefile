.PHONY: install-dev lint type test format ci pre-commit

install-dev:
	python -m pip install --upgrade pip
	pip install -e .[dev]

lint:
	ruff check .

format:
	ruff check --fix .

type:
	mypy .

test:
	pytest

pre-commit:
	pre-commit install
	pre-commit run --all-files

ci: lint type test


