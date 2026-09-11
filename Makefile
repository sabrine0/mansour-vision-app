# MANSOUR Vision — task runner.
#
# Windows developers: `make` is not present by default. Every target below has an
# npm-script or direct equivalent; see docs/development.md. CI is Linux and uses
# this file.

.DEFAULT_GOAL := help
SHELL := /bin/bash

PY := .venv/bin/python
PACKAGES := packages/py-common packages/contracts
SERVICES := services/core-api services/vision-worker services/alert-engine services/analytics-consumer
MYPY_PACKAGES := -p mansour_common -p mansour_contracts -p mansour_api \
                 -p mansour_vision_worker -p mansour_alert_engine -p mansour_analytics
COMPOSE := docker compose -f infra/compose/docker-compose.yml

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# --- Setup ------------------------------------------------------------------

.PHONY: install
install: ## Create the venv, install every Python package and the npm workspace
	python -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install $(foreach p,$(PACKAGES),-e $(p)[test]) $(foreach s,$(SERVICES),-e $(s)[test])
	$(PY) -m pip install ruff mypy pytest-cov
	npm install

.PHONY: secrets
secrets: ## Generate the local development secrets Compose expects
	@mkdir -p infra/secrets
	@test -f infra/secrets/postgres_password || openssl rand -base64 32 > infra/secrets/postgres_password
	@test -f infra/secrets/redis_password || openssl rand -base64 32 > infra/secrets/redis_password
	@chmod 600 infra/secrets/* 2>/dev/null || true
	@echo "secrets ready in infra/secrets/"

# --- Quality ----------------------------------------------------------------

.PHONY: lint
lint: ## Ruff + ESLint
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	npm run lint

.PHONY: format
format: ## Autofix formatting and import order
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .
	npm run format

.PHONY: typecheck
typecheck: ## Strict mypy + tsc
	$(PY) -m mypy $(MYPY_PACKAGES)
	npm run typecheck

.PHONY: test
test: ## Every test, Python and frontend
	$(PY) -m pytest -m "not integration"
	npm run test

.PHONY: test-integration
test-integration: ## Tests that need a live PostgreSQL and Redis
	$(PY) -m pytest -m integration

.PHONY: coverage
coverage: ## Python coverage report
	$(PY) -m pytest --cov --cov-report=term-missing --cov-report=html -m "not integration"

.PHONY: check
check: lint typecheck contracts-check test ## Everything CI runs, locally

# --- Contracts --------------------------------------------------------------

.PHONY: contracts
contracts: ## Regenerate JSON Schemas and TypeScript types from the pydantic models
	$(PY) -m mansour_contracts.export --out packages/contracts/schema
	npm run contracts:generate

.PHONY: contracts-check
contracts-check: ## Fail if the generated contracts are stale
	$(PY) -m mansour_contracts.export --check --out packages/contracts/schema
	npm run contracts:check

# --- Database ---------------------------------------------------------------

.PHONY: migrate
migrate: ## Apply migrations
	cd services/core-api && ../../$(PY) -m alembic upgrade head

.PHONY: migration
migration: ## Create a migration: make migration m="add cameras table"
	cd services/core-api && ../../$(PY) -m alembic revision -m "$(m)"

.PHONY: migrate-sql
migrate-sql: ## Print the SQL a migration would run, without connecting
	cd services/core-api && ../../$(PY) -m alembic upgrade head --sql

# --- Stack ------------------------------------------------------------------

.PHONY: up
up: secrets ## Start the whole stack
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Stop the stack, keep the volumes
	$(COMPOSE) down

.PHONY: nuke
nuke: ## Stop the stack and destroy its data. Irreversible.
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Tail every service
	$(COMPOSE) logs -f --tail=100

.PHONY: ps
ps: ## Service status
	$(COMPOSE) ps

.PHONY: compose-check
compose-check: secrets ## Validate the Compose file
	$(COMPOSE) config --quiet && echo "compose configuration is valid"

# --- Licensing (ADR 0002) ---------------------------------------------------

.PHONY: license-check
license-check: ## Fail if a copyleft dependency has entered the tree
	$(PY) -m pip install --quiet pip-licenses
	$(PY) -m piplicenses --fail-on="GNU Affero General Public License v3;GNU General Public License v3 (GPLv3);GNU General Public License v2 (GPLv2);Server Side Public License (SSPL)"
	@! $(PY) -m pip show ultralytics > /dev/null 2>&1 || \
		(echo "ERROR: ultralytics is installed. It is AGPL-3.0. See docs/adr/0002." && exit 1)
	@echo "no copyleft dependency present"
