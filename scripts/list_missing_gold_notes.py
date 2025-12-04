#!/usr/bin/env python3
"""
Compare gold/gold_LOCAL.jsonl against LOCAL predictions and list missing note_ids.
Outputs data/missing_note_ids.txt (one per line).
"""

from __future__ import annotations

import json
from pathlib import Path

GOLD_PATH = Path("gold/gold_LOCAL.jsonl")
PRED_PATH = Path("fixtures/enriched/entities/run=LOCAL/part-000.jsonl")
OUTPUT_PATH = Path("data/missing_note_ids.txt")


def load_note_ids(path: Path) -> set[str]:
    ids = set()
    if not path.exists():
        return ids
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            note_id = record.get("note_id")
            if note_id:
                ids.add(note_id)
    return ids


def main() -> None:
    gold_ids = load_note_ids(GOLD_PATH)
    pred_ids = load_note_ids(PRED_PATH)

    missing = sorted(gold_ids - pred_ids)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(missing))

    print(
        "[coverage-report] "
        f"gold_notes={len(gold_ids)} "
        f"pred_notes={len(pred_ids)} "
        f"missing={len(missing)} "
        f"output={OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
