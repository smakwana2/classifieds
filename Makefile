VENV   ?= .venv
PYTHON := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip
MANAGE := $(PYTHON) manage.py

# Optional arguments, e.g. `make test T=ads.tests.AdTestCase` or `make makemigrations APP=ads`
T   ?=
APP ?=

.DEFAULT_GOAL := help
.PHONY: help venv install migrate makemigrations seed setup run test shell check clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

$(PYTHON):
	python3 -m venv $(VENV)

venv: $(PYTHON) ## Create the virtualenv if missing

install: $(PYTHON) ## Install requirements into the virtualenv
	$(PIP) install -r requirements.txt

migrate: ## Apply database migrations
	$(MANAGE) migrate

makemigrations: ## Create migrations (optionally APP=ads)
	$(MANAGE) makemigrations $(APP)

seed: ## Seed starter categories (idempotent)
	$(MANAGE) seed_categories

setup: install migrate seed ## Install, migrate and seed in one go

run: ## Start the development server
	$(MANAGE) runserver

test: ## Run tests (optionally T=ads or T=ads.tests.SomeTest)
	$(MANAGE) test $(T)

shell: ## Open a Django shell
	$(MANAGE) shell

check: ## Run Django system checks and check for missing migrations
	$(MANAGE) check
	$(MANAGE) makemigrations --check --dry-run

clean: ## Remove Python bytecode caches
	find . -path ./$(VENV) -prune -o -type d -name __pycache__ -exec rm -rf {} +
