.DEFAULT_GOAL := help
.PHONY: help install fmt lint typecheck test cov check build clean hooks

PY ?= python3
VENV := .venv
UV := uv

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Create .venv and install the package with dev extras
	$(UV) venv --python 3.12 $(VENV)
	$(UV) pip install -e ".[dev]"
	@echo "Activate with: source $(VENV)/bin/activate"

hooks: ## Install git pre-commit hooks
	pre-commit install --install-hooks

fmt: ## Apply formatting and auto-fixes
	ruff check --fix src tests noxfile.py
	ruff format src tests noxfile.py

lint: ## Lint and verify formatting (no writes)
	ruff check src tests noxfile.py
	ruff format --check --diff src tests noxfile.py

typecheck: ## Run mypy in strict mode
	mypy

test: ## Run the test suite
	pytest

cov: ## Run tests and open an HTML coverage report
	pytest --cov-report=html
	@echo "open htmlcov/index.html"

check: lint typecheck test ## Everything CI runs, in CI's order

build: clean ## Build sdist + wheel and validate metadata
	$(UV) build
	$(UV)x twine check --strict dist/*

clean: ## Remove build, cache and coverage artifacts
	rm -rf dist build *.egg-info htmlcov .coverage .coverage.* coverage.xml
	rm -rf .pytest_cache .mypy_cache .ruff_cache .hypothesis .nox
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
