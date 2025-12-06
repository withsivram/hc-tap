"""
Manifest Schema Standardization

This file documents the standardized manifest schema used across HC-TAP services.
All services should write and read manifests following this schema.

## Standard Manifest Schema (v2)

```json
{
  "manifest_version": 2,
  "run_id": "string",
  "extractor": "string (rule|spacy|llm|etc)",
  "ts_started": "ISO 8601 timestamp",
  "ts_finished": "ISO 8601 timestamp",
  "ts": "ISO 8601 timestamp (alias for ts_finished)",
  "note_count": "integer",
  "entity_count": "integer",
  "duration_ms_p50": "integer (milliseconds)",
  "duration_ms_p95": "integer (milliseconds)",
  "errors": "integer (count of errors)",
  "error_rate": "float (0.0 to 1.0)",
  "f1_exact_micro": "float or null",
  "f1_relaxed_micro": "float or null",
  "f1_exact_micro_intersection": "float or null",
  "f1_relaxed_micro_intersection": "float or null",
  "status": "string (success|failed|partial)",
  "extractor_metrics": {
    "<extractor_name>": {
      "f1_exact_micro": "float",
      "f1_relaxed_micro": "float",
      ... additional metrics
    }
  }
}
```

## Migration Notes

### Old Schemas

**etl_local.py (old):**
- Used manifest_version, ts_started, ts_finished
- Missing error_rate
- Had processed_notes instead of note_count

**rule_extract.py (old):**
- Used p50_ms, p95_ms (should be duration_ms_p50, duration_ms_p95)
- Used processed_notes instead of note_count
- Missing manifest_version

**dashboard.py reads:**
- Expects extractor_metrics dict
- Falls back to flat f1_* fields

### Migration Path

1. Update all manifest writers to use v2 schema
2. Update readers to handle both v1 and v2 for backward compatibility
3. After migration, readers can simplify

## Implementation Status

- [ ] etl_local.py - Update to v2 schema
- [ ] rule_extract.py - Update to v2 schema
- [ ] etl_cloud.py - Update to v2 schema
- [ ] dashboard.py - Add v2 compatibility
- [ ] eval scripts - Add v2 compatibility
"""
