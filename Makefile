.PHONY: test
test:
	python scripts/validate_fixtures.py

.PHONY: etl-stub
etl-stub:
	python services/etl/etl_stub.py

