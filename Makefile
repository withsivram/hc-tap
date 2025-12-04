.PHONY: docker-up docker-down docker-build docker-etl docker-logs \
	test etl-stub api-stub dash extract-local ingest download-data \
	ingest-50 ingest-100 validate etl-local etl-spacy etl-llm eval judge \
	bootstrap format lint gold-init clean help

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down

docker-build:
	docker-compose build

docker-etl:
	docker-compose run --rm etl

docker-logs:
	docker-compose logs -f --tail=200

test:
	pytest -q

etl-stub:
	python services/etl/etl_stub.py

api-stub:
	python -m uvicorn services.api.app:app --reload --port 8000

dash:
	streamlit run services/analytics/streamlit_app.py

extract-local:
	python services/etl/rule_extract.py

ingest:
	python services/etl/ingest.py

download-data:
	python scripts/download_data.py

ingest-50:
	python scripts/ingest_mtsamples.py --count 50

ingest-100:
	python scripts/ingest_mtsamples.py --count 100

validate:
	@[ -f .env ] || ( [ -f .env.template ] && cp .env.template .env && echo "Created .env from template" )
	python scripts/validate_notes.py

etl-local: validate
	python services/etl/etl_local.py

etl-spacy:
	EXTRACTOR=spacy python services/etl/etl_local.py

etl-llm:
	EXTRACTOR=llm python services/etl/etl_local.py

eval:
	python services/eval/evaluate_entities.py

judge:
	python services/eval/judge.py

bootstrap:
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	[ -f requirements-dev.txt ] && pip install -r requirements-dev.txt || true
	python -m spacy download en_core_sci_sm || true
	pre-commit install
	python scripts/check_env.py

format:
	black .
	isort .

lint:
	ruff check .

gold-init:
	python scripts/bootstrap_gold.py

clean:
	rm -f fixtures/entities/*.jsonl
	rm -rf fixtures/enriched/entities/run=LOCAL

help:
	@echo "Available commands:"
	@printf "  %-15s %s\n" "docker-up" "Start docker-compose stack (builds images)."
	@printf "  %-15s %s\n" "docker-down" "Stop all docker-compose services."
	@printf "  %-15s %s\n" "docker-build" "Build docker images without running."
	@printf "  %-15s %s\n" "docker-etl" "Run ETL service within docker-compose."
	@printf "  %-15s %s\n" "docker-logs" "Tail docker-compose logs."
	@printf "  %-15s %s\n" "test" "Run pytest suite."
	@printf "  %-15s %s\n" "etl-stub" "Replay fixture entities into enriched output."
	@printf "  %-15s %s\n" "api-stub" "Start FastAPI stub with uvicorn."
	@printf "  %-15s %s\n" "dash" "Launch the Streamlit dashboard."
	@printf "  %-15s %s\n" "extract-local" "Run rule extractor utility directly."
	@printf "  %-15s %s\n" "ingest" "Legacy ingest pipeline (services/etl/ingest.py)."
	@printf "  %-15s %s\n" "download-data" "Download supporting datasets."
	@printf "  %-15s %s\n" "ingest-50" "Ingest 50 notes from MTSamples CSV."
	@printf "  %-15s %s\n" "ingest-100" "Ingest 100 notes from MTSamples CSV."
	@printf "  %-15s %s\n" "validate" "Validate fixtures/notes via JSON schema."
	@printf "  %-15s %s\n" "etl-local" "Run rule-based ETL (validates first)."
	@printf "  %-15s %s\n" "etl-spacy" "Run ETL using the spaCy extractor."
	@printf "  %-15s %s\n" "etl-llm" "Run ETL using the LLM extractor."
	@printf "  %-15s %s\n" "eval" "Evaluate LOCAL predictions vs. gold."
	@printf "  %-15s %s\n" "judge" "Run the LLM judge evaluation script."
	@printf "  %-15s %s\n" "bootstrap" "Install dependencies and pre-commit hooks."
	@printf "  %-15s %s\n" "format" "Run black + isort formatters."
	@printf "  %-15s %s\n" "lint" "Run Ruff lint checks."
	@printf "  %-15s %s\n" "gold-init" "Generate gold fixtures from notes."
	@printf "  %-15s %s\n" "clean" "Remove local enriched entity artifacts."
	@printf "  %-15s %s\n" "help" "Show this command list."
