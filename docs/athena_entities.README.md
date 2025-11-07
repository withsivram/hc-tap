# analytics_entities (Athena)

**Schema** (JSON Lines):

- note_id (string)
- run_id (string)
- entity_type (string) — e.g., PROBLEM, MEDICATION, TEST
- text (string) — original text span
- norm_text (string) — normalized form
- begin, end (int) — character offsets
- score (double) — model confidence
- section (string) — e.g., 'Assessment', 'Plan'

**Partitioning**

- `run` is an S3 partition (folder) like `enriched/entities/run=2025-10-29-01/`.

**Location**

- The LOCATION is a placeholder for now and will be set by infra.
- This doc is for alignment; the dashboard runs locally on JSONL fixtures.

**Local emulation**

- We validate columns using pandas/DuckDB in tests (no real Athena required).

