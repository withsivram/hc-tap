#!/usr/bin/env python3
"""
Ingest rows from the MTSamples CSV into fixtures/notes as note_{i:03d}.json files.
Skips existing notes and reports how many were written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

NOTES_DIR = Path("fixtures/notes")
DEFAULT_SOURCE = Path("data/MTSamples.csv")


def read_rows(csv_path: Path, start: int, count: int):
    import pandas as pd  # Lazy import per dependency constraints

    df = pd.read_csv(csv_path)
    return df.iloc[start : start + count]


def checksum(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def write_note(path: Path, note_id: str, text: str, specialty: str) -> None:
    payload = {
        "note_id": note_id,
        "specialty": specialty,
        "text": text,
        "checksum": checksum(text),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def ingest(csv_path: Path, start: int, count: int) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"MTSamples CSV not found at {csv_path}")

    rows = read_rows(csv_path, start, count)
    written = 0
    skipped = 0

    for offset, (_, row) in enumerate(rows.iterrows()):
        seq = start + offset
        note_id = f"note_{seq:03d}"
        target = NOTES_DIR / f"{note_id}.json"
        if target.exists():
            skipped += 1
            continue
        transcription = str(row.get("transcription") or "").strip()
        if not transcription:
            skipped += 1
            continue
        specialty = str(row.get("medical_specialty") or "Unknown").strip() or "Unknown"
        write_note(target, note_id, transcription, specialty)
        written += 1

    print(
        f"[ingest] source={csv_path} start={start} requested={count} written={written} skipped={skipped}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest notes from MTSamples CSV.")
    parser.add_argument(
        "--count", type=int, default=50, help="Number of notes to ingest."
    )
    parser.add_argument(
        "--start", type=int, default=0, help="Row offset within the CSV to start from."
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    csv_path = Path(os.getenv("MTSAMPLES_CSV", DEFAULT_SOURCE))
    ingest(csv_path, max(args.start, 0), max(args.count, 0))


if __name__ == "__main__":
    main()
