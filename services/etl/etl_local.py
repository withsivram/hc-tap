#!/usr/bin/env python3
"""
Local ETL orchestrator (Pluggable version):
1. Load raw notes
2. Preprocess
3. Extract entities (via chosen EXTRACTOR)
4. Write enriched JSONL
5. Update run manifest
"""

import glob
import json
import os
import sys
import time

from dotenv import load_dotenv

# Ensure we can import from services
sys.path.append(os.getcwd())
load_dotenv()

from services.etl.preprocess import normalize_text  # noqa: E402
from services.etl.rule_extract import (median_ms, quantile_ms,  # noqa: E402
                                       utc_now_iso)
from services.extractors.llm_extract import LLMExtractor  # noqa: E402
from services.extractors.spacy_extract import SpacyExtractor  # noqa: E402

NOTES_DIR = "fixtures/notes"
RUN_MANIFEST_PATH = "fixtures/runs_LOCAL.json"


def get_extractor():
    name = os.getenv("EXTRACTOR", "spacy").lower()
    if name == "llm":
        return name, LLMExtractor()
    return "spacy", SpacyExtractor()


def main():
    extractor_name, extractor = get_extractor()
    print(f"[etl] Using extractor: {extractor_name}")

    # Enriched dir varies by extractor to allow side-by-side comparison
    enriched_dir = f"fixtures/enriched/entities/run={extractor_name}"
    os.makedirs(enriched_dir, exist_ok=True)

    note_paths = sorted(glob.glob(os.path.join(NOTES_DIR, "*.json")))
    per_note_times = []
    notes_seen = 0
    entities_total = 0

    ts_started = utc_now_iso()

    # Prepare output file
    enriched_path = os.path.join(enriched_dir, "part-000.jsonl")

    # Run ID for the entities
    run_id = extractor_name.upper()

    # Optional Limit
    limit = int(os.getenv("LIMIT", "0"))

    with open(enriched_path, "w", encoding="utf-8") as out_f:
        for np in note_paths:
            if limit > 0 and notes_seen >= limit:
                break

            with open(np, "r", encoding="utf-8") as f:
                note = json.load(f)

            note_id = note["note_id"]
            raw_text = note["text"]
            notes_seen += 1

            t0 = time.perf_counter()

            # Preprocess
            text = normalize_text(raw_text)

            # Extract
            entities = extractor.extract(text, note_id, run_id)

            for ent in entities:
                # If entity is an object (from extractor), dump it
                # If it's a dict, dump it directly
                if hasattr(ent, "__dict__"):
                    out_f.write(json.dumps(ent.__dict__) + "\n")
                else:
                    out_f.write(json.dumps(ent) + "\n")
                entities_total += 1

            t1 = time.perf_counter()
            per_note_times.append(t1 - t0)

    # Update manifest
    ts_finished = utc_now_iso()

    # We read the existing manifest first to preserve other extractors' data
    manifest = {}
    if os.path.exists(RUN_MANIFEST_PATH):
        try:
            with open(RUN_MANIFEST_PATH, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            pass

    # Update top-level fields to reflect THIS run (the most recent one)
    manifest.update(
        {
            "run_id": run_id,
            "extractor": extractor_name,
            "ts_started": ts_started,
            "ts_finished": ts_finished,
            "note_count": notes_seen,
            "entity_count": entities_total,
            "duration_ms_p50": median_ms(per_note_times),
            "duration_ms_p95": quantile_ms(per_note_times, 0.95),
            "errors": 0,
            "ts": ts_finished,
        }
    )

    with open(RUN_MANIFEST_PATH, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)

    print(
        f"ETL ({extractor_name}) OK ✅  notes={notes_seen}  entities={entities_total}"
    )
    print(f"enriched: {enriched_path}")
    print(f"manifest: {RUN_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
