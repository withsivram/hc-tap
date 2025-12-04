import json
import os

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

APP_RUN_ID = "LOCAL"
NOTES_DIR = "fixtures/notes"
ENRICHED_FILE = f"fixtures/enriched/entities/run={APP_RUN_ID}/part-000.jsonl"
RUN_MANIFEST = "fixtures/runs_LOCAL.json"

app = FastAPI(title="HC-TAP API", version="1.0.0")


def load_notes():
    notes = {}
    if not os.path.exists(NOTES_DIR):
        return notes
    for name in os.listdir(NOTES_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(NOTES_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            notes[obj["note_id"]] = obj
        except Exception:
            pass
    return notes


def load_entities_index():
    """Return (all_entities_list, by_note_id_dict)."""
    all_ents = []
    by_note = {}
    if not os.path.exists(ENRICHED_FILE):
        return all_ents, by_note
    with open(ENRICHED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ent = json.loads(line)
                all_ents.append(ent)
                by_note.setdefault(ent["note_id"], []).append(ent)
            except Exception:
                pass
    return all_ents, by_note


# Load data
NOTES = load_notes()
ALL_ENTS, ENTS_BY_NOTE = load_entities_index()


def reload_data():
    global NOTES, ALL_ENTS, ENTS_BY_NOTE
    NOTES = load_notes()
    ALL_ENTS, ENTS_BY_NOTE = load_entities_index()


@app.get("/notes/{note_id}")
def get_note(note_id: str):
    reload_data()
    note = NOTES.get(note_id)
    if not note:
        return JSONResponse(
            status_code=404, content={"error": "not_found", "message": "note not found"}
        )

    entities = ENTS_BY_NOTE.get(note_id, [])
    return {
        "note_id": note["note_id"],
        "specialty": note.get("specialty"),
        "text": note.get("text"),
        "checksum": note.get("checksum"),
        "entities": entities,
    }


@app.get("/stats/run/{run_id}")
def get_run_stats(run_id: str):
    if run_id != "LOCAL":
        return JSONResponse(
            status_code=404, content={"error": "not_found", "message": "run not found"}
        )

    if not os.path.exists(RUN_MANIFEST):
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "message": "manifest not found"},
        )

    try:
        with open(RUN_MANIFEST, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "message": "manifest invalid"},
        )

    return {
        "run_id": manifest.get("run_id"),
        "note_count": manifest.get("note_count", manifest.get("notes_total")),
        "entity_count": manifest.get("entity_count", manifest.get("entities_total")),
        "f1_exact_micro": manifest.get("f1_exact_micro"),
        "f1_relaxed_micro": manifest.get("f1_relaxed_micro"),
        "ts": manifest.get("ts", manifest.get("ts_finished")),
    }


@app.get("/search")
def search_entities(
    q: str | None = None,
    type: str | None = Query(None, pattern="^(PROBLEM|MEDICATION)$"),
    limit: int = 50,
):
    if limit < 1 or limit > 200:
        return JSONResponse(
            status_code=400,
            content={
                "error": "bad_request",
                "message": "invalid query parameter 'limit', must be 1..200",
            },
        )

    reload_data()
    items = ALL_ENTS

    if type:
        items = [e for e in items if e.get("entity_type") == type]

    if q:
        ql = q.lower()
        # scan enriched over norm_text substring
        items = [
            e
            for e in items
            if (e.get("norm_text") and ql in e.get("norm_text").lower())
        ]

    return items[:limit]
