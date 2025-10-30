.PHONY: test
test:
	python scripts/validate_fixtures.py

.PHONY: etl-stub
etl-stub:
	python services/etl/etl_stub.py

.PHONY: api-stub
api-stub:
	python -m uvicorn services.api.app:app --reload --port 8000

.PHONY: dash
dash:
	streamlit run services/analytics/dashboard.py
