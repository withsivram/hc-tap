#!/usr/bin/env python3
"""
Promote curated draft entities into gold/gold_LOCAL.jsonl.

Sources:
1. docs/curation/NOTE_*.md — rows with “[x] approve”
2. gold/gold_DRAFT.jsonl (fallback) with source="bootstrap"
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from services.etl.preprocess import normalize_entity_text, normalize_text  # noqa: E402

CURATION_DIR = Path("docs/curation")
DRAFT_PATH = Path("gold/gold_DRAFT.jsonl")
GOLD_PATH = Path("gold/gold_LOCAL.jsonl")
NOTES_DIR = Path("fixtures/notes")

CURATION_ROW_RE = re.compile(
    r"^\|\s*(?P<type>PROBLEM|MEDICATION)\s*\|\s*(?P<text>.+?)\s*\|\s*(?P<begin>.*?)\|\s*(?P<end>.*?)\|\s*\[(?P<approved>[xX\s])\]\s*approve\s*\|$"
)


def load_note(note_id: str, cache: Dict[str, Dict]) -> Dict | None:
    if note_id in cache:
        return cache[note_id]
    path = NOTES_DIR / f"{note_id}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        cache[note_id] = json.load(fh)
    return cache[note_id]


def find_span(note_text: str, raw_text: str) -> Tuple[int, int] | None:
    norm_text = normalize_entity_text(raw_text)
    if not norm_text:
        return None
    normalized_note = normalize_text(note_text)
    lower_note = normalized_note.lower()
    idx = lower_note.find(norm_text)
    if idx == -1:
        return None
    return idx, idx + len(norm_text)


def parse_curation_files() -> List[Dict]:
    rows: List[Dict] = []
    if not CURATION_DIR.exists():
        return rows
    for path in sorted(CURATION_DIR.glob("NOTE_*.md")):
        note_id = path.stem.replace("NOTE_", "")
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                match = CURATION_ROW_RE.match(line.strip())
                if not match:
                    continue
                if match.group("approved").lower() != "x":
                    continue
                entity = {
                    "note_id": note_id,
                    "entity_type": match.group("type"),
                    "text": match.group("text").strip(),
                }
                rows.append(entity)
    return rows


def fallback_bootstrap() -> List[Dict]:
    if not DRAFT_PATH.exists():
        return []
    rows = []
    with DRAFT_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("source") == "bootstrap":
                rows.append(record)
    return rows


def load_existing() -> List[Dict]:
    if not GOLD_PATH.exists():
        return []
    with GOLD_PATH.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def dedupe_key(record: Dict) -> Tuple:
    return (
        record.get("note_id"),
        record.get("entity_type"),
        int(record.get("begin", 0) or 0),
        int(record.get("end", 0) or 0),
        normalize_entity_text(record.get("norm_text")),
    )


def promote() -> Tuple[int, int, int]:
    curated = parse_curation_files()
    if not curated:
        curated = fallback_bootstrap()
        source = "bootstrap draft"
    else:
        source = "curation pack"

    if not curated:
        print("[gold-promote] No curated or bootstrap entries found.")
        return 0, 0, 0

    existing = load_existing()
    existing_keys = {dedupe_key(row) for row in existing}

    added = 0
    duplicates = 0
    unmatched = 0
    note_cache: Dict[str, Dict] = {}

    for entry in curated:
        note_id = entry.get("note_id")
        entity_type = entry.get("entity_type")
        raw_text = entry.get("text")
        if not note_id or entity_type not in {"PROBLEM", "MEDICATION"} or not raw_text:
            unmatched += 1
            continue

        note = load_note(note_id, note_cache)
        if not note:
            unmatched += 1
            continue

        span = find_span(note.get("text", ""), raw_text)
        if not span or span[0] >= span[1]:
            unmatched += 1
            continue

        record = {
            "note_id": note_id,
            "entity_type": entity_type,
            "text": note.get("text", "")[span[0] : span[1]],
            "norm_text": normalize_entity_text(raw_text),
            "begin": span[0],
            "end": span[1],
            "source": source,
        }
        key = dedupe_key(record)
        if key in existing_keys:
            duplicates += 1
            continue
        existing_keys.add(key)
        existing.append(record)
        added += 1

    GOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(GOLD_PATH.parent), delete=False
    ) as tmp:
        for row in existing:
            tmp.write(json.dumps(row, ensure_ascii=False) + "\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, GOLD_PATH)
    print(
        f"[gold-promote] source={source} added={added} duplicates={duplicates} unmatched={unmatched}"
    )
    return added, duplicates, unmatched


def main() -> None:
    promote()


if __name__ == "__main__":
    main()
