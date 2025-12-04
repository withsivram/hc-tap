#!/usr/bin/env python3
"""
Generate lightweight markdown curation packs for draft gold entities.

Usage:
    python scripts/curation_pack.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

DRAFT_PATH = Path("gold/gold_DRAFT.jsonl")
NOTES_DIR = Path("fixtures/notes")
OUTPUT_DIR = Path("docs/curation")
MAX_NOTES = int(os.getenv("CURATION_LIMIT", "30"))
NOTE_CHAR_LIMIT = 2000


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


def get_note_text(note_id: str) -> str:
    note_path = NOTES_DIR / f"{note_id}.json"
    if not note_path.exists():
        return "(note text not found)"
    with note_path.open("r", encoding="utf-8") as fh:
        note = json.load(fh)
    text = note.get("text") or ""
    if len(text) > NOTE_CHAR_LIMIT:
        text = text[:NOTE_CHAR_LIMIT] + "\n\n... (truncated) ..."
    return text


def format_entity_table(rows: List[Dict]) -> str:
    lines = [
        "| Type | Text | Begin | End | Approve |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        entity_type = row.get("entity_type", "")
        text = (row.get("text") or "").replace("\n", " ")
        begin = row.get("begin", "")
        end = row.get("end", "")
        lines.append(f"| {entity_type} | {text} | {begin} | {end} | [ ] approve |")
    return "\n".join(lines)


def write_markdown(note_id: str, rows: List[Dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    note_text = get_note_text(note_id)
    md = [
        f"# Note {note_id}",
        "",
        "## Note Text",
        "",
        "```",
        note_text,
        "```",
        "",
        "## Draft Entities",
        "",
        format_entity_table(rows),
        "",
    ]
    path = OUTPUT_DIR / f"NOTE_{note_id}.md"
    path.write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    draft_rows = load_jsonl(DRAFT_PATH)
    if not draft_rows:
        print(
            f"[curation-pack] No draft entities found at {DRAFT_PATH}. Run `make gold-bootstrap` first."
        )
        return

    by_note: Dict[str, List[Dict]] = {}
    for row in draft_rows:
        note_id = row.get("note_id")
        if not note_id:
            continue
        by_note.setdefault(note_id, []).append(row)

    selected_notes = sorted(by_note.keys())[:MAX_NOTES]
    if not selected_notes:
        print("[curation-pack] No eligible notes found in draft file.")
        return

    for note_id in selected_notes:
        write_markdown(note_id, by_note[note_id])

    print(
        f"[curation-pack] Wrote {len(selected_notes)} markdown files to {OUTPUT_DIR}/NOTE_<id>.md"
    )


if __name__ == "__main__":
    main()
