# Entry point for the usual tasks. Docker is the only prerequisite: nothing is installed on the host.
# make is a convenience, never a requirement: every target is one command, shown in its recipe, and
# "docker compose up -d" alone is enough to start the application.
.DEFAULT_GOAL := help
.PHONY: help up down logs build pull test typecheck smoke dockerhub-description

COMPOSE ?= docker compose
# Git Bash on Windows rewrites arguments that look like paths before Docker sees them
export MSYS_NO_PATHCONV = 1
export MSYS2_ARG_CONV_EXCL = *

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

up: ## Start the application (http://localhost:8080)
	$(COMPOSE) up -d

down: ## Stop the application (the volumes are kept)
	$(COMPOSE) down

logs: ## Follow the logs
	$(COMPOSE) logs -f --tail=100

build: ## Build the images from this checkout, pulling the newest base images (applies security updates)
	$(COMPOSE) build --pull

pull: ## Fetch the published images (skouedlabs/portal-ng-*)
	$(COMPOSE) pull

test: ## Run the frontend test suite (Homer import/export, routing)
	docker run --rm -v "$(CURDIR)/frontend:/app" -w /app node:24-alpine sh -c 'npm ci && npm test'

typecheck: ## Build the frontend, which is what catches a broken component
	docker run --rm -v "$(CURDIR)/frontend:/app" -w /app node:24-alpine sh -c 'npm ci && npm run build'

# What CI calls "the stack starts and answers": it starts the real compose file and asks the running
# application a few questions. The unit tests cover logic; this covers the thing actually running.
smoke: ## Start the stack, check that it answers, then tear it down
	$(COMPOSE) up -d --build --wait --wait-timeout 300
	curl -fsS http://127.0.0.1:8080/api/health | grep -q '"status":"ok"'
	curl -fsS http://127.0.0.1:8080/api/public/config | grep -q portal_name
	curl -fsS http://127.0.0.1:8080/ | grep -q '<div id="app">'
	curl -fsS -o /dev/null http://127.0.0.1:8080/logo.png
	! $(COMPOSE) logs backend | grep -q 'Traceback (most recent call last)'
	@echo "ok"
	$(COMPOSE) down -v

dockerhub-description: ## Render the Docker Hub description of both images without uploading anything
	sh scripts/dockerhub-description.sh backend --print
	sh scripts/dockerhub-description.sh frontend --print
