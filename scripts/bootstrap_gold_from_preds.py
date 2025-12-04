#!/usr/bin/env python3
"""
Bootstrap draft gold labels from LOCAL predictions for quick manual review.

Usage:
    python scripts/bootstrap_gold_from_preds.py

Writes candidate entities for up to BOOTSTRAP_LIMIT (default 20) note_ids that
are present in LOCAL predictions but missing from the current gold file.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

PRED_PATH = Path("fixtures/enriched/entities/run=LOCAL/part-000.jsonl")
GOLD_PATH = Path("gold/gold_LOCAL.jsonl")
DRAFT_PATH = Path("gold/gold_DRAFT.jsonl")
BOOTSTRAP_LIMIT = int(os.getenv("BOOTSTRAP_LIMIT", "20"))


def load_jsonl(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def gather_note_ids(rows: Iterable[Dict]) -> set[str]:
    return {row.get("note_id") for row in rows if row.get("note_id")}


def main() -> None:
    preds = load_jsonl(PRED_PATH)
    if not preds:
        print(
            f"[gold-bootstrap] No predictions found at {PRED_PATH}. Run `make etl-local` first."
        )
        return

    gold_records = load_jsonl(GOLD_PATH)
    gold_note_ids = gather_note_ids(gold_records)

    target_note_ids: List[str] = []
    seen: set[str] = set()
    for row in preds:
        note_id = row.get("note_id")
        if not note_id or note_id in gold_note_ids or note_id in seen:
            continue
        seen.add(note_id)
        target_note_ids.append(note_id)
        if len(target_note_ids) >= BOOTSTRAP_LIMIT:
            break

    if not target_note_ids:
        print(
            "[gold-bootstrap] All predicted notes already exist in gold. Nothing to bootstrap."
        )
        return

    DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with DRAFT_PATH.open("w", encoding="utf-8") as fh:
        for row in preds:
            if row.get("note_id") not in target_note_ids:
                continue
            draft_row = dict(row)
            draft_row["source"] = "bootstrap"
            fh.write(json.dumps(draft_row, ensure_ascii=False) + "\n")
            count += 1

    print(
        "[gold-bootstrap] "
        f"draft_entities={count} "
        f"notes={len(target_note_ids)} "
        f"output={DRAFT_PATH}"
    )
    print(
        "[gold-bootstrap] Review the draft file, promote validated entries into "
        "`gold_LOCAL.jsonl`, then rerun `make gold-sync`."
    )


if __name__ == "__main__":
    main()
