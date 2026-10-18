.PHONY: install lint format typecheck test test-bats sql-lint check secret-scan emulator extract load dbt export metrics \
        pipeline demo up down pipeline-docker demo-docker alerts-test tf-validate dashboard backlog

RAW ?= data/raw

install:            ## Python deps incl. the emulator and dev tools
	uv sync --all-extras

lint:
	uv run ruff check . && uv run ruff format --check .

format:
	uv run ruff format . && uv run ruff check --fix .

typecheck:
	uv run mypy

test:               ## loader, exports, metrics and CLI against an in-process Snowflake emulator, with coverage
	uv run pytest --cov=rx --cov-report=term-missing --cov-report=xml

test-bats:          ## the Bash extractor and orchestrator
	shellcheck scripts/*.sh && bats tests/bats

check: lint typecheck test test-bats

secret-scan:        ## run before every push
	bash scripts/secret_scan.sh

emulator:           ## local Snowflake (fakesnow) on 127.0.0.1:8085, in memory
	uv run rx emulator

extract:            ## all planned dataset-years from the CMS API into $(RAW) (~3.2 GB, ~25 min)
	uv run rx plan | while IFS="$$(printf '\t')" read -r ds year id state; do \
	  bash scripts/extract_cms.sh "$$id" "$(RAW)/$$ds/$$year" $$( [ "$$state" = "-" ] || echo "$$state" ); done

pipeline:           ## extract (if not done) -> load -> dbt build -> export -> metrics, against `make emulator`
	RX_RAW_DIR=$(RAW) uv run bash scripts/run_pipeline.sh

demo:               ## the same pipeline on the committed CI sample (seconds, no download; results in .demo/)
	RX_RAW_DIR=tests/fixtures/pages SKIP_EXTRACT=1 RX_REPORTS_DIR=.demo/reports RX_EXPORTS_DIR=.demo/exports \
	  DBT_TARGET_PATH=$(CURDIR)/.demo/dbt-target uv run bash scripts/run_pipeline.sh

up:                 ## emulator, Pushgateway, Prometheus and Grafana in Docker
	docker compose up -d --build --wait --wait-timeout 300 emulator pushgateway prometheus grafana

down:
	docker compose down -v

pipeline-docker:    ## one batch in Docker against the compose emulator (extracts into ./data/raw first)
	docker compose run --rm --build pipeline

demo-docker:        ## the committed sample through the Docker pipeline (reports into .demo/, not reports/)
	mkdir -p .demo/reports .demo/exports && RX_HOST_RAW_DIR=./tests/fixtures/pages RX_HOST_REPORTS_DIR=./.demo/reports \
	  RX_HOST_EXPORTS_DIR=./.demo/exports SKIP_EXTRACT=1 docker compose run --rm --build pipeline

alerts-test:
	docker run --rm -v "$(CURDIR)/observability:/w" -w /w --entrypoint promtool prom/prometheus:v3.5.0 test rules alerts_test.yml

tf-validate:
	terraform -chdir=infra/terraform fmt -check -recursive && terraform -chdir=infra/terraform init -backend=false \
	  -input=false && terraform -chdir=infra/terraform validate

dashboard:
	uv run python scripts/make_dashboard.py

backlog:            ## labels, milestones and issues on GitHub from docs/agile/backlog.json
	python scripts/agile/sync_backlog.py
