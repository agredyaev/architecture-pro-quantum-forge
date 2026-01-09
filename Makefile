# QuantumForge RAG Bot - Makefile

.PHONY: help install setup-env lint lint-fix check all-checks download anonymize ingest pipeline update-index logs-clean demo security-demo retrieval evaluate diagrams-svg bot docker-build docker-etl docker-up docker-down docker-logs clean clean-index

.DEFAULT_GOAL := help

PLANTUML_JAR := $(CURDIR)/plantuml.jar

help: ## Show the list of targets
	@awk 'BEGIN {FS=":.*##"; OFS=""} \
		/^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0,5); next} \
		/^[a-zA-Z0-9_.-]+:.*##/ {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ Setup

install: ## Install dependencies
	uv sync

setup-env: ## Create .env from template
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example - edit it with your API keys"; \
	else \
		echo ".env already exists"; \
	fi

##@ Development

lint: ## Run ruff linter
	uv run ruff check src/

lint-fix: ## Run ruff with auto-fix
	uv run ruff check src/ --fix

check: ## Run type checker (ty)
	uv run ty check src/

all-checks: lint check ## Run lint + type check

##@ Data Pipeline

download: ## Download wiki data
	uv run python -m src.data_gen.download_wiki

anonymize: ## Anonymize raw data
	uv run python -m src.data_gen.anonymize

ingest: ## Ingest data into vector DB
	uv run python -m src.data_gen.ingest

pipeline: download anonymize ingest ## Run full data pipeline

update-index: ## Incrementally update knowledge base index (Task 6)
	uv run python -m src.data_gen.update_index

logs-clean: ## Clean log files
	rm -rf logs/*.log logs/*.json

##@ Testing

demo: ## Run RAG demo dialogs
	uv run python -m src.data_gen.test_rag

security-demo: ## Run security tests (Task 5)
	uv run python -m src.data_gen.security_demo

retrieval: ## Test retrieval quality
	uv run python -m src.data_gen.test_retrieval

evaluate: ## Run RAG quality evaluation (Task 7)
	uv run python -m src.data_gen.evaluate

verify-project: security-demo update-index evaluate ## Run all project verification tasks (5, 6, 7)

##@ Docs

diagrams-svg: ## Regenerate PlantUML SVG diagrams
	@if [ ! -f "$(PLANTUML_JAR)" ]; then \
		echo "plantuml.jar not found in project root"; \
		exit 1; \
	fi
	@if ! command -v java >/dev/null 2>&1; then \
		echo "java not found in PATH"; \
		exit 1; \
	fi
	@cd docs/diagrams/src && java -jar "$(PLANTUML_JAR)" -tsvg -o ../img *.puml

##@ Bot

bot: ## Start Telegram bot
	uv run python -m src.bot.main

##@ Docker

docker-build: ## Build Docker image
	docker compose build

docker-etl: ## Run ETL pipeline (download, anonymize, ingest)
	docker compose --profile etl run --rm etl

docker-up: ## Start bot and redis
	docker compose up -d bot redis

docker-down: ## Stop all services
	docker compose down

docker-logs: ## View bot logs
	docker compose logs -f bot

docker-prune: ## Clean volumes, dangling images, and build cache
	docker compose down -v
	docker system prune -f
	docker builder prune -f

##@ Cleanup

clean: ## Remove caches and temp files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache 2>/dev/null || true

clean-index: ## Remove vector indexes
	rm -rf data/chroma_storage data/colbert_index
