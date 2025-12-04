from __future__ import annotations

import datetime
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Tuple

RUN_ID = os.getenv("RUN_ID", "LOCAL")
NOTES_DIR = Path("fixtures/notes")
ENRICHED_DIR = Path(f"enriched/entities/run={RUN_ID}")
RUN_MANIFEST_PATH = Path("runs/runs_local.json")

PROBLEM_TERMS = ["hypertension", "chest tightness", "diabetes", "asthma"]
MEDICATION_TERMS = ["metformin", "lisinopril", "atorvastatin", "ibuprofen"]
DOSAGE_RE = r"(?:\s+\d+\s*(?:mg|mcg|g))?"

REQUIRED_KEYS = [
    "note_id",
    "run_id",
    "entity_type",
    "text",
    "norm_text",
    "begin",
    "end",
    "score",
    "section",
]


def utc_iso() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def median_ms(samples: List[float]) -> float:
    if not samples:
        return 0.0
    xs = sorted(samples)
    n = len(xs)
    if n % 2:
        return float(int(round(xs[n // 2] * 1000)))
    return float(int(round((xs[n // 2 - 1] + xs[n // 2]) / 2 * 1000)))


def quantile_ms(samples: List[float], q: float) -> float:
    if not samples:
        return 0.0
    xs = sorted(samples)
    k = max(1, math.ceil(q * len(xs)))
    return float(int(round(xs[k - 1] * 1000)))


def load_notes() -> Iterator[Dict]:
    for path in sorted(NOTES_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as fh:
            yield json.load(fh)


def find_spans(
    text: str, terms: Iterable[str], with_dose: bool = False
) -> Iterator[Tuple[int, int, str, str]]:
    flags = re.IGNORECASE
    for term in terms:
        pattern = (
            rf"\b({re.escape(term)}){DOSAGE_RE}\b"
            if with_dose
            else rf"\b({re.escape(term)})\b"
        )
        for match in re.finditer(pattern, text, flags):
            yield match.start(), match.end(), text[
                match.start() : match.end()
            ], match.group(1).lower()


def guess_section(text: str, begin: int) -> str:
    window = text[max(0, begin - 60) : begin + 60].lower()
    if "assessment" in window or "impression" in window:
        return "Assessment"
    if "started on" in window or "taking " in window:
        return "Plan"
    return "unknown"


def ensure_contract(row: Dict) -> Dict:
    for key in REQUIRED_KEYS:
        row.setdefault(key, None)
    return row


def extract_for_note(note: Dict) -> List[Dict]:
    note_id = note.get("note_id")
    text = note.get("text", "") or ""
    if not note_id or not text:
        return []

    rows: List[Dict] = []

    for begin, end, span, norm in find_spans(text, PROBLEM_TERMS, with_dose=False):
        rows.append(
            dict(
                note_id=note_id,
                run_id=RUN_ID,
                entity_type="PROBLEM",
                text=span,
                norm_text=norm,
                begin=begin,
                end=end,
                score=0.90,
                section=guess_section(text, begin),
            )
        )

    for begin, end, span, norm in find_spans(text, MEDICATION_TERMS, with_dose=True):
        rows.append(
            dict(
                note_id=note_id,
                run_id=RUN_ID,
                entity_type="MEDICATION",
                text=span,
                norm_text=norm,
                begin=begin,
                end=end,
                score=0.95,
                section=guess_section(text, begin),
            )
        )

    return rows


def write_entities(rows: Iterable[Dict], sink: Path) -> int:
    written = 0
    with sink.open("a", encoding="utf-8") as fh:
        for row in rows:
            ensure_contract(row)
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
    return written


def update_manifest(processed_notes: int, p50: float, p95: float) -> None:
    record = {
        "run_id": RUN_ID,
        "p50_ms": p50,
        "p95_ms": p95,
        "error_rate": 0.0,
        "processed_notes": processed_notes,
        "ts": utc_iso(),
    }

    RUN_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest: List[Dict] = []

    if RUN_MANIFEST_PATH.exists():
        try:
            with RUN_MANIFEST_PATH.open("r", encoding="utf-8") as fh:
                existing = json.load(fh)
            if isinstance(existing, list):
                manifest = [r for r in existing if str(r.get("run_id")) != str(RUN_ID)]
        except Exception:
            manifest = []

    manifest.append(record)
    with RUN_MANIFEST_PATH.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)


def main() -> None:
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    out_file = ENRICHED_DIR / "entities_local.jsonl"
    out_file.write_text("", encoding="utf-8")

    per_note_durations: List[float] = []
    notes_seen = 0
    entities_written = 0

    for note in load_notes():
        start = time.perf_counter()
        rows = extract_for_note(note)
        if rows:
            entities_written += write_entities(rows, out_file)
        notes_seen += 1 if note.get("note_id") else 0
        per_note_durations.append(time.perf_counter() - start)

    p50 = median_ms(per_note_durations)
    p95 = quantile_ms(per_note_durations, 0.95)
    update_manifest(notes_seen, p50, p95)

    print(f"[rule_extract] notes={notes_seen} entities={entities_written} → {out_file}")
    print(f"[rule_extract] manifest → {RUN_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
