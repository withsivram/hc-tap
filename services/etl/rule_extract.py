#!/usr/bin/env python3
"""
Local rule-based extractor:
- Reads fixtures/notes/*.json
- Finds PROBLEM & MEDICATION spans via simple regex/lexicons
- Writes per-note JSONL in fixtures/entities/{note_id}.jsonl
- Bundles all into fixtures/enriched/entities/run=LOCAL/part-000.jsonl
- Updates fixtures/runs_LOCAL.json with p50/p95 and counts
"""

import datetime
import glob
import json
import math
import os
import re
import time

NOTES_DIR = "fixtures/notes"
ENTITIES_DIR = "fixtures/entities"
ENRICHED_DIR = "fixtures/enriched/entities/run=LOCAL"
RUN_MANIFEST_PATH = "fixtures/runs_LOCAL.json"

# Tiny lexicons (extend as needed)
PROBLEM_TERMS = ["hypertension", "chest tightness", "diabetes", "asthma"]
MEDICATION_TERMS = ["metformin", "lisinopril", "atorvastatin", "ibuprofen"]

DOSAGE_RE = r"(?:\s+\d+\s*(?:mg|mcg|g))?"  # optional dose like " 10 mg"


def utc_now_iso():
    return (
        datetime.datetime.now(datetime.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def quantile_ms(values, q):
    if not values:
        return 0
    xs = sorted(values)
    # nearest-rank method (conservative)
    k = max(1, math.ceil(q * len(xs)))
    return int(round(xs[k - 1] * 1000))


def median_ms(values):
    if not values:
        return 0
    xs = sorted(values)
    n = len(xs)
    if n % 2 == 1:
        return int(round(xs[n // 2] * 1000))
    return int(round((xs[n // 2 - 1] + xs[n // 2]) / 2 * 1000))


def find_spans(text, terms, with_dose=False):
    flags = re.IGNORECASE
    spans = []
    for term in terms:
        # build pattern
        if with_dose:
            pat = rf"\b({re.escape(term)}){DOSAGE_RE}\b"
        else:
            pat = rf"\b({re.escape(term)})\b"
        for m in re.finditer(pat, text, flags):
            span_text = text[m.start() : m.end()]
            norm = m.group(1).lower()
            spans.append((m.start(), m.end(), span_text, norm))
    return spans


def guess_section(text, begin):
    # super simple heuristic
    window = text[max(0, begin - 40) : begin + 40].lower()
    if "started on" in window or "taking " in window:
        return "medications"
    if "assessment" in window or "impression" in window:
        return "assessment"
    return "unknown"


def main():
    os.makedirs(ENTITIES_DIR, exist_ok=True)
    os.makedirs(ENRICHED_DIR, exist_ok=True)

    note_paths = sorted(glob.glob(os.path.join(NOTES_DIR, "*.json")))
    per_note_times = []
    notes_seen = 0
    entities_total = 0

    ts_started = utc_now_iso()

    # Per-note JSONL files
    for np in note_paths:
        with open(np, "r", encoding="utf-8") as f:
            note = json.load(f)
        note_id = note["note_id"]
        text = note["text"]
        notes_seen += 1

        t0 = time.perf_counter()

        # Problems
        for b, e, span_text, norm in find_spans(text, PROBLEM_TERMS, with_dose=False):
            obj = {
                "note_id": note_id,
                "run_id": "LOCAL",
                "entity_type": "PROBLEM",
                "text": span_text,
                "norm_text": norm,
                "begin": b,
                "end": e,
                "score": 0.90,
                "section": guess_section(text, b),
            }
            out_path = os.path.join(ENTITIES_DIR, f"{note_id}.jsonl")
            with open(out_path, "a", encoding="utf-8") as out_f:
                out_f.write(json.dumps(obj) + "\n")
            entities_total += 1

        # Medications (allow optional dose)
        for b, e, span_text, norm in find_spans(text, MEDICATION_TERMS, with_dose=True):
            obj = {
                "note_id": note_id,
                "run_id": "LOCAL",
                "entity_type": "MEDICATION",
                "text": span_text,
                "norm_text": norm,
                "begin": b,
                "end": e,
                "score": 0.95,
                "section": guess_section(text, b),
            }
            out_path = os.path.join(ENTITIES_DIR, f"{note_id}.jsonl")
            with open(out_path, "a", encoding="utf-8") as out_f:
                out_f.write(json.dumps(obj) + "\n")
            entities_total += 1

        t1 = time.perf_counter()
        per_note_times.append(t1 - t0)

    # Bundle to enriched/part-000.jsonl
    enriched_path = os.path.join(ENRICHED_DIR, "part-000.jsonl")
    with open(enriched_path, "w", encoding="utf-8") as out_f:
        for np in note_paths:
            nid = os.path.splitext(os.path.basename(np))[0]
            src = os.path.join(ENTITIES_DIR, f"{nid}.jsonl")
            if os.path.exists(src):
                with open(src, "r", encoding="utf-8") as sf:
                    for line in sf:
                        if line.strip():
                            out_f.write(line)

    # Update manifest with fresh p50/p95
    ts_finished = utc_now_iso()
    manifest = {
        "run_id": "LOCAL",
        "ts_started": ts_started,
        "ts_finished": ts_finished,
        "notes_total": notes_seen,
        "entities_total": entities_total,
        "duration_ms_p50": median_ms(per_note_times),
        "duration_ms_p95": quantile_ms(per_note_times, 0.95),
        "errors": 0,
    }
    with open(RUN_MANIFEST_PATH, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)

    print(f"Rule extract OK ✅  notes={notes_seen}  entities={entities_total}")
    print(f"enriched: {enriched_path}")
    print(f"manifest: {RUN_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
