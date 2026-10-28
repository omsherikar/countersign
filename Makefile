.DEFAULT_GOAL := help
COMPOSE ?= docker compose

help: ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

up: ## build and start every service
	$(COMPOSE) up -d --build

down: ## stop everything, keep volumes
	$(COMPOSE) down

nuke: ## stop everything and drop volumes
	$(COMPOSE) down -v

logs: ## follow logs
	$(COMPOSE) logs -f --tail=100

datagen: ## generate synthetic data (small by default; SIZE=full for 500 colleges)
	$(COMPOSE) --profile tools run --rm datagen generate --size $${SIZE:-small} --seed $${SEED:-42} --out /data/generated

seed: ## load generated data: mockgov registries first, then every upload through the api engine
	$(COMPOSE) run --rm mockgov python -m app.seed --from /data/generated/mockgov
	$(COMPOSE) run --rm api python -m app.seed.cli --from /data/generated

demo-reset: ## wipe both databases and reseed, mockgov first
	$(COMPOSE) run --rm mockgov python -m app.seed --reset --from /data/generated/mockgov
	$(COMPOSE) run --rm api python -m app.seed.cli --reset --from /data/generated

test: ## run every test suite inside compose
	$(COMPOSE) run --rm api pytest -q
	$(COMPOSE) run --rm mockgov pytest -q
	$(COMPOSE) --profile tools run --rm datagen pytest -q

eval: ## run the accuracy evaluation (Week 4)
	@echo "eval arrives in Week 4"

.PHONY: help up down nuke logs datagen seed demo-reset test eval
