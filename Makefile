.PHONY: help install dev test lint scan clean build

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install passclip
	pip install .

dev: ## Install with all optional deps for development
	pip install -e ".[all,dev]"

test: ## Run tests
	python -m pytest tests/ -v

lint: ## Run ruff linter
	ruff check passclip.py

scan: ## Scan for hardcoded credentials (dry-run)
	credactor --dry-run .

clean: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info __pycache__ .pytest_cache .ruff_cache
	find . -name '*.pyc' -delete

build: ## Build package for PyPI
	python -m build
