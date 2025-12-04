#!/usr/bin/env python3
"""
Realign gold spans to the current normalized note text so begin/end offsets stay meaningful.

Usage:
    python scripts/sync_gold_offsets.py

Writes an updated `gold/gold_LOCAL.jsonl` via atomic replacement.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from services.etl.preprocess import normalize_entity_text, normalize_text  # noqa: E402

GOLD_PATH = Path("gold/gold_LOCAL.jsonl")
NOTES_DIR = Path("fixtures/notes")
VALID_TYPES = {"PROBLEM", "MEDICATION"}
MAX_EDIT_DISTANCE = 1


def load_note(note_id: str, cache: Dict[str, Dict]) -> Dict | None:
    if note_id in cache:
        return cache[note_id]
    path = NOTES_DIR / f"{note_id}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        cache[note_id] = json.load(fh)
    return cache[note_id]


def within_edit_distance_one(a: str, b: str) -> bool:
    if a == b:
        return True
    len_a, len_b = len(a), len(b)
    if abs(len_a - len_b) > MAX_EDIT_DISTANCE:
        return False
    if len_a == len_b:
        mismatches = sum(ch1 != ch2 for ch1, ch2 in zip(a, b))
        return mismatches <= MAX_EDIT_DISTANCE
    # ensure len_a < len_b
    if len_a > len_b:
        a, b = b, a
        len_a, len_b = len_b, len_a
    i = j = 0
    edits = 0
    while i < len_a and j < len_b:
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > MAX_EDIT_DISTANCE:
            return False
        j += 1  # skip one char in the longer string
    # account for trailing char
    if j < len_b or i < len_a:
        edits += 1
    return edits <= MAX_EDIT_DISTANCE


def fuzzy_find(note_lower: str, target: str) -> Tuple[int, int] | None:
    if not target:
        return None
    n = len(target)
    lengths = tuple(
        length for length in {n - 1, n, n + 1} if 0 < length <= len(note_lower)
    )
    for length in lengths:
        for start in range(0, len(note_lower) - length + 1):
            candidate = note_lower[start : start + length]
            if within_edit_distance_one(candidate, target):
                return start, start + length
    return None


def realign_gold() -> Tuple[int, int]:
    GOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
    note_cache: Dict[str, Dict] = {}
    matched = 0
    unmatched = 0

    if not GOLD_PATH.exists():
        raise FileNotFoundError(f"Gold file not found at {GOLD_PATH}")

    with GOLD_PATH.open("r", encoding="utf-8") as fh, tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(GOLD_PATH.parent),
        delete=False,
        suffix=".tmp",
    ) as tmp_f:
        tmp_path = Path(tmp_f.name)
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            note_id = record.get("note_id")
            if not note_id:
                record["unmatched"] = True
                unmatched += 1
                tmp_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                continue

            note = load_note(note_id, note_cache)
            if not note:
                record["unmatched"] = True
                unmatched += 1
                tmp_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                continue

            entity_type = record.get("entity_type")
            if entity_type not in VALID_TYPES:
                record["unmatched"] = True
                unmatched += 1
                tmp_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                continue

            note_text = normalize_text(note.get("text", ""))
            note_lower = note_text.lower()

            raw_text = record.get("text") or record.get("norm_text") or ""
            norm_text = normalize_entity_text(raw_text)

            start = note_lower.find(norm_text)
            end = start + len(norm_text) if start != -1 else -1

            if start == -1:
                fuzzy = fuzzy_find(note_lower, norm_text)
                if fuzzy:
                    start, end = fuzzy

            if start == -1 or end == -1 or start >= end:
                record["unmatched"] = True
                unmatched += 1
            else:
                snippet = note_text[start:end]
                record["begin"] = start
                record["end"] = end
                record["text"] = snippet
                record["norm_text"] = normalize_entity_text(snippet)
                record.pop("unmatched", None)
                matched += 1

            tmp_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    os.replace(tmp_path, GOLD_PATH)
    return matched, unmatched


def main() -> None:
    matched, unmatched = realign_gold()
    print(f"[gold-sync] aligned={matched} unmatched={unmatched} output={GOLD_PATH}")


if __name__ == "__main__":
    main()
