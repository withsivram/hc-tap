#!/usr/bin/env python3
"""Local ETL stub: bundles fixture entity lines into enriched/ JSONL and writes a run manifest."""

import os, glob, json, time, datetime

NOTES_DIR = "fixtures/notes"
SRC_ENTITIES_DIR = "fixtures/entities"
ENRICHED_DIR = "fixtures/enriched/entities/run=LOCAL"
RUN_MANIFEST_PATH = "fixtures/runs_LOCAL.json"


def utc_now_iso():
    # Normalize UTC offset to 'Z' for ISO 8601 compliance
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace("+00:00", "Z")


def main():
    os.makedirs(ENRICHED_DIR, exist_ok=True)
    out_path = os.path.join(ENRICHED_DIR, "part-000.jsonl")

    note_paths = sorted(glob.glob(os.path.join(NOTES_DIR, "*.json")))
    notes_seen = 0
    entities_written = 0

    ts_started = utc_now_iso()

    with open(out_path, "w", encoding="utf-8") as out_f:
        for np in note_paths:
            with open(np, "r", encoding="utf-8") as nf:
                note = json.load(nf)
            note_id = note.get("note_id")
            if not note_id:
                continue
            notes_seen += 1

            src_jsonl = os.path.join(SRC_ENTITIES_DIR, f"{note_id}.jsonl")
            if not os.path.exists(src_jsonl):
                # no entities for this note in fixtures; skip silently
                continue

            with open(src_jsonl, "r", encoding="utf-8") as ef:
                for line in ef:
                    line = line.strip()
                    if not line:
                        continue
                    out_f.write(line + "\n")
                    entities_written += 1

    # Simple manifest (using placeholders for duration p50/p95)
    ts_finished = utc_now_iso()
    manifest = {
        "run_id": "LOCAL",
        "ts_started": ts_started,
        "ts_finished": ts_finished,
        "notes_total": notes_seen,
        "entities_total": entities_written,
        "duration_ms_p50": 0,
        "duration_ms_p95": 0,
        "errors": 0
    }
    with open(RUN_MANIFEST_PATH, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)

    print(f"ETL stub OK ✅  notes={notes_seen}  entities={entities_written}")
    print(f"wrote: {out_path}")
    print(f"manifest: {RUN_MANIFEST_PATH}")

if __name__ == "__main__":
    main()
