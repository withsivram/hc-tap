#!/usr/bin/env python3
"""
Validate fixtures/notes/*.json against contracts/note.schema.json,
enforcing unique note_id and non-empty text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

NOTES_DIR = Path("fixtures/notes")
NOTE_SCHEMA = Path("contracts/note.schema.json")


def load_schema(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    if not NOTE_SCHEMA.exists():
        print(f"[validate] Schema not found at {NOTE_SCHEMA}")
        return 1

    schema = load_schema(NOTE_SCHEMA)
    validator = Draft202012Validator(schema)

    note_ids = set()
    errors = []

    for note_path in sorted(NOTES_DIR.glob("*.json")):
        with note_path.open("r", encoding="utf-8") as fh:
            try:
                note = json.load(fh)
            except json.JSONDecodeError as exc:
                errors.append(f"{note_path}: invalid JSON ({exc})")
                continue

        for err in validator.iter_errors(note):
            errors.append(f"{note_path}: {err.message}")

        note_id = note.get("note_id")
        if not note_id:
            errors.append(f"{note_path}: missing note_id")
        else:
            if note_id in note_ids:
                errors.append(f"{note_path}: duplicate note_id '{note_id}'")
            note_ids.add(note_id)

        text = (note.get("text") or "").strip()
        if not text:
            errors.append(f"{note_path}: text is empty after stripping whitespace")

    if errors:
        print("[validate] FAIL")
        for err in errors:
            print(f"  - {err}")
        print(f"[validate] {len(errors)} issue(s) found across {len(note_ids)} notes")
        return 1

    print(f"[validate] OK — validated {len(note_ids)} notes against {NOTE_SCHEMA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
