from __future__ import annotations

import datetime
import json
from pathlib import Path

# External contract: keep these paths/names stable.
RUN_ID = Path().resolve().joinpath().name and "LOCAL"
NOTES_DIR = Path("fixtures/notes")
SRC_ENTITIES_DIR = Path("fixtures/entities")
ENRICHED_DIR = Path(f"enriched/entities/run={RUN_ID}")
RUN_MANIFEST_PATH = Path("runs/runs_local.json")

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


def iso_utc() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_note_files() -> list[Path]:
    return sorted(NOTES_DIR.glob("*.json"))


def iter_entities_for_note(note_id: str):
    src = SRC_ENTITIES_DIR / f"{note_id}.jsonl"
    if not src.exists():
        return
    with src.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def normalize_entity(obj: dict, note: dict) -> dict:
    obj.setdefault("run_id", RUN_ID)
    obj.setdefault("norm_text", note.get("text", ""))
    obj.setdefault("section", note.get("section", "unknown"))
    for key in REQUIRED_KEYS:
        obj.setdefault(key, None)
    return obj


def write_manifest(processed_notes: int) -> None:
    record = {
        "run_id": RUN_ID,
        "p50_ms": 0.0,
        "p95_ms": 0.0,
        "error_rate": 0.0,
        "processed_notes": processed_notes,
    }

    RUN_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest: list = []

    if RUN_MANIFEST_PATH.exists():
        try:
            with RUN_MANIFEST_PATH.open("r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, list):
                manifest = [r for r in existing if str(r.get("run_id")) != str(RUN_ID)]
        except Exception:
            # If the file is unreadable, start fresh.
            manifest = []

    manifest.append(record)
    with RUN_MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def main() -> None:
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    out_file = ENRICHED_DIR / "entities_part1.jsonl"

    # Start clean; then append.
    out_file.write_text("", encoding="utf-8")

    notes_seen = 0
    ents_written = 0

    with out_file.open("a", encoding="utf-8") as sink:
        for note_path in iter_note_files():
            note = read_json(note_path)
            note_id = note.get("note_id")
            if not note_id:
                continue

            notes_seen += 1

            for ent in iter_entities_for_note(note_id):
                ent = normalize_entity(ent, note)
                sink.write(json.dumps(ent, ensure_ascii=False) + "\n")
                ents_written += 1

    write_manifest(notes_seen)

    print(f"[etl_stub] notes={notes_seen} entities={ents_written} → {out_file}")
    print(f"[etl_stub] manifest → {RUN_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
