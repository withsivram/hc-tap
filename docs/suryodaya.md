Analytics & Viz lane (Suryodaya)

This dashboard reads local JSONL outputs (enriched/entities/run=<ID>) and shows basic KPIs (processed notes, entities, p50/p95 latency, error rate) and top-10 entities for Problems and Medications, plus searchable full results with CSV export.

When infra is ready, the same schema maps to S3/Athena: we set the table LOCATION in contracts/athena_entities.ddl and swap the local file loader for an S3/Athena reader. No UI changes needed—only the data source adapter.

