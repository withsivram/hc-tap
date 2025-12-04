#!/usr/bin/env python3
"""
Phase-3 ETL orchestrator:
  1. Load fixtures/notes/*.json deterministically
  2. Normalize text
  3. Run rule-based extractor
  4. Emit fixtures/enriched/entities/run=LOCAL/part-000.jsonl
  5. Merge-update fixtures/runs_LOCAL.json (atomic write)
"""

from __future__ import annotations

import json
import math
import os
import random
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List

from services.etl import rule_extract
from services.etl.preprocess import normalize_entity_text, normalize_text

RUN_ID = "LOCAL"
EXTRACTOR_NAME = "rule"
NOTES_DIR = Path("fixtures/notes")
ENRICHED_DIR = Path("fixtures/enriched/entities/run=LOCAL")
OUTPUT_FILE = ENRICHED_DIR / "part-000.jsonl"
MANIFEST_PATH = Path("fixtures/runs_LOCAL.json")
HC_DEBUG = os.getenv("HC_TAP_DEBUG", "0") == "1"
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "1337"))
random.seed(RANDOM_SEED)


def log(message: str, *, debug: bool = False) -> None:
    if debug and not HC_DEBUG:
        return
    prefix = "[ETL]"
    if debug:
        prefix = f"{prefix}[debug]"
    print(f"{prefix} {message}")


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def median_ms(samples: List[float]) -> int:
    if not samples:
        return 0
    xs = sorted(samples)
    n = len(xs)
    if n % 2:
        return int(round(xs[n // 2] * 1000))
    return int(round((xs[n // 2 - 1] + xs[n // 2]) / 2 * 1000))


def quantile_ms(samples: List[float], q: float) -> int:
    if not samples:
        return 0
    xs = sorted(samples)
    k = max(1, math.ceil(q * len(xs)))
    return int(round(xs[k - 1] * 1000))


def iter_note_paths() -> Iterable[Path]:
    return sorted(NOTES_DIR.glob("*.json"))


def normalize_entity(entity: Dict, note_id: str) -> Dict:
    entity.setdefault("note_id", note_id)
    entity.setdefault("run_id", RUN_ID)
    entity["norm_text"] = normalize_entity_text(entity.get("text"))
    begin = int(entity.get("begin", 0) or 0)
    end = int(entity.get("end", 0) or 0)
    if begin >= end:
        raise ValueError(f"Invalid span ({begin}, {end}) for note {note_id}")
    entity["begin"] = begin
    entity["end"] = end
    return entity


def atomic_write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), delete=False
    ) as fh:
        json.dump(payload, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
        tmp_name = fh.name
    os.replace(tmp_name, path)


def atomic_write_jsonl(path: Path, records: Iterable[Dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), delete=False
    ) as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")
            written += 1
        fh.flush()
        os.fsync(fh.fileno())
        tmp_name = fh.name
    os.replace(tmp_name, path)
    return written


class EntityEmitter:
    def __init__(self) -> None:
        self.limit = int(os.getenv("LIMIT", "0") or 0)
        self.notes_seen = 0
        self.entities_total = 0
        self.per_note_durations: List[float] = []
        self.sample: List[Dict] = []
        self.ts_started = utc_now_iso()
        self.ts_finished = self.ts_started

    def __iter__(self) -> Iterator[Dict]:
        for note_path in iter_note_paths():
            if self.limit and self.notes_seen >= self.limit:
                break
            with note_path.open("r", encoding="utf-8") as fh:
                note = json.load(fh)
            note_id = note.get("note_id")
            if not note_id:
                continue
            text = normalize_text(note.get("text", ""))
            note_payload = dict(note, text=text)
            start = time.perf_counter()
            entities = rule_extract.extract_for_note(note_payload) or []
            self.notes_seen += 1
            for entity in entities:
                normalized = normalize_entity(entity, note_id)
                if len(self.sample) < 3:
                    self.sample.append(normalized.copy())
                self.entities_total += 1
                yield normalized
            duration = time.perf_counter() - start
            self.per_note_durations.append(duration)
            log(
                f"note={note_id} ents={len(entities)} duration_ms={duration*1000:.1f}",
                debug=True,
            )
        self.ts_finished = utc_now_iso()

    @property
    def stats(self) -> Dict:
        return {
            "notes_seen": self.notes_seen,
            "entities_total": self.entities_total,
            "ts_started": self.ts_started,
            "ts_finished": self.ts_finished,
            "duration_ms_p50": median_ms(self.per_note_durations),
            "duration_ms_p95": quantile_ms(self.per_note_durations, 0.95),
            "sample": self.sample,
        }


def update_manifest(stats: Dict) -> None:
    manifest: Dict = {}
    if MANIFEST_PATH.exists():
        try:
            with MANIFEST_PATH.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                manifest = loaded
        except Exception:
            manifest = {}
    manifest.update(
        {
            "manifest_version": 1,
            "run_id": RUN_ID,
            "extractor": EXTRACTOR_NAME,
            "ts_started": stats["ts_started"],
            "ts_finished": stats["ts_finished"],
            "ts": stats["ts_finished"],
            "note_count": stats["notes_seen"],
            "entity_count": stats["entities_total"],
            "duration_ms_p50": stats["duration_ms_p50"],
            "duration_ms_p95": stats["duration_ms_p95"],
            "errors": 0,
        }
    )
    atomic_write_json(MANIFEST_PATH, manifest)


def main() -> None:
    log("Starting LOCAL ETL via rule extractor")
    emitter = EntityEmitter()
    entities_written = atomic_write_jsonl(OUTPUT_FILE, emitter)
    stats = emitter.stats
    update_manifest(stats)
    log(
        f"completed notes={stats.get('notes_seen', 0)} entities={entities_written} "
        f"output={OUTPUT_FILE}"
    )
    log(f"manifest updated {MANIFEST_PATH}")
    if stats.get("sample") and HC_DEBUG:
        log(
            f"sample entities={json.dumps(stats['sample'], ensure_ascii=False)}",
            debug=True,
        )


if __name__ == "__main__":
    main()
