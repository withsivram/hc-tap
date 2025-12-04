#!/usr/bin/env python3
"""
Ingest MTSamples CSV data into individual JSON note files.
"""

import csv
import hashlib
import json
import os
import sys

# Try to load from .env manually if dotenv not installed (kept lightweight)
ENV_FILE = ".env"
MTSAMPLES_CSV = None

if os.path.exists(ENV_FILE):
    with open(ENV_FILE, "r") as f:
        for line in f:
            if line.startswith("MTSAMPLES_CSV="):
                MTSAMPLES_CSV = line.strip().split("=", 1)[1]
                break

# Fallback or command line override could go here
if not MTSAMPLES_CSV:
    MTSAMPLES_CSV = "./data/MTSamples.csv"

NOTES_DIR = "fixtures/notes"


def get_note_id(idx: int) -> str:
    return f"note_{idx:03d}"


def clean_text(text: str) -> str:
    return " ".join(text.split()).strip()


def ingest():
    if not os.path.exists(MTSAMPLES_CSV):
        print(f"[ingest] CSV not found at {MTSAMPLES_CSV}. Skipping ingestion.")
        print("Tip: Download MTSamples.csv to data/ or update .env")
        return

    print(f"[ingest] Reading from {MTSAMPLES_CSV}...")
    os.makedirs(NOTES_DIR, exist_ok=True)

    count = 0
    try:
        with open(MTSAMPLES_CSV, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                # Expected columns: "medical_specialty", "transcription", ...
                # We use 'transcription' as text.
                text = row.get("transcription", "")
                if not text:
                    continue

                text = clean_text(text)
                specialty = row.get("medical_specialty", "Unknown")

                note_id = get_note_id(i)
                checksum = hashlib.md5(text.encode("utf-8")).hexdigest()

                note = {
                    "note_id": note_id,
                    "specialty": specialty,
                    "text": text,
                    "checksum": checksum,
                }

                out_path = os.path.join(NOTES_DIR, f"{note_id}.json")
                with open(out_path, "w", encoding="utf-8") as out_f:
                    json.dump(note, out_f, indent=2)

                count += 1
                if count % 100 == 0:
                    print(f"  Processed {count} notes...", end="\r")

    except Exception as e:
        print(f"\n[ingest] Error reading CSV: {e}")
        sys.exit(1)

    print(f"\n[ingest] Successfully ingested {count} notes into {NOTES_DIR}/")


if __name__ == "__main__":
    ingest()
