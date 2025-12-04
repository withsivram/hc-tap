.PHONY: docker-up
docker-up:
	docker-compose up --build

.PHONY: docker-down
docker-down:
	docker-compose down

.PHONY: docker-build
docker-build:
	docker-compose build

.PHONY: docker-etl
docker-etl:
	docker-compose run --rm etl

.PHONY: docker-logs
docker-logs:
	docker-compose logs -f --tail=200

.PHONY: test
test:
	pytest tests/

.PHONY: etl-stub
etl-stub:
	python services/etl/etl_stub.py

.PHONY: api-stub
api-stub:
	python -m uvicorn services.api.app:app --reload --port 8000

.PHONY: dash
dash:
	streamlit run services/analytics/dashboard.py

.PHONY: extract-local
extract-local:
	python services/etl/rule_extract.py

.PHONY: ingest
ingest:
	python services/etl/ingest.py

.PHONY: download-data
download-data:
	python scripts/download_data.py


.PHONY: etl-local
etl-local:
	python services/etl/etl_local.py

.PHONY: etl-spacy
etl-spacy:
	EXTRACTOR=spacy python services/etl/etl_local.py

.PHONY: etl-llm
etl-llm:
	EXTRACTOR=llm python services/etl/etl_local.py


.PHONY: bootstrap
bootstrap:
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	[ -f requirements-dev.txt ] && pip install -r requirements-dev.txt || true
	python -m spacy download en_core_sci_sm || true
	pre-commit install
	[ ! -f .env ] && cp .env.template .env && echo "Copied .env.template to .env" || true
	python scripts/check_env.py

.PHONY: format
format:
	black .
	isort .

.PHONY: lint
lint:
	ruff check .

.PHONY: gold-init
gold-init:
	python scripts/bootstrap_gold.py

.PHONY: help
help:
	@echo "Targets: bootstrap | extract-local | eval | api-stub | dash | clean | gold-init"

.PHONY: eval
eval:
	python services/eval/evaluate_entities.py

.PHONY: judge
judge:
	python services/eval/judge.py

.PHONY: clean
clean:
	rm -f fixtures/entities/*.jsonl
	rm -rf fixtures/enriched/entities/run=LOCAL

