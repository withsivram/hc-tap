from fastapi import FastAPI, HTTPException, Query
import json, os

APP_RUN_ID = "LOCAL"
NOTES_DIR = "fixtures/notes"
ENRICHED_FILE = f"fixtures/enriched/entities/run={APP_RUN_ID}/part-000.jsonl"
RUN_MANIFEST = "fixtures/runs_LOCAL.json"

app = FastAPI(title="HC-TAP API (Stub)", version="1.0.0")

def load_notes():
    notes = {}
    for name in os.listdir(NOTES_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(NOTES_DIR, name)
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        notes[obj["note_id"]] = obj
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
            ent = json.loads(line)
            all_ents.append(ent)
            by_note.setdefault(ent["note_id"], []).append(ent)
    return all_ents, by_note

NOTES = load_notes()
ALL_ENTS, ENTS_BY_NOTE = load_entities_index()

@app.get("/notes/{note_id}")
def get_note(note_id: str):
    note = NOTES.get(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="note not found")
    entities = ENTS_BY_NOTE.get(note_id, [])
    # return full note for stub; you can trim text later if you like
    return {
        "note_id": note["note_id"],
        "specialty": note["specialty"],
        "text": note["text"],
        "checksum": note["checksum"],
        "entities": entities,
    }

@app.get("/stats/run/{run_id}")
def get_run_stats(run_id: str):
    if run_id != APP_RUN_ID:
        raise HTTPException(status_code=404, detail="run not found")
    if not os.path.exists(RUN_MANIFEST):
        raise HTTPException(status_code=404, detail="manifest not found")
    with open(RUN_MANIFEST, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    return manifest

@app.get("/search")
def search_entities(
    type: str | None = Query(None, pattern="^(PROBLEM|MEDICATION)$"),
    q: str | None = None,
    limit: int = Query(10, ge=1, le=100),
    cursor: int = Query(0, ge=0),
):
    items = ALL_ENTS
    if type:
        items = [e for e in items if e.get("entity_type") == type]
    if q:
        ql = q.lower()
        items = [e for e in items if ql in e.get("norm_text","").lower() or ql in e.get("text","").lower()]
    total = len(items)
    end = min(cursor + limit, total)
    page = items[cursor:end]
    next_cursor = end if end < total else None
    return {"count": total, "items": page, "next_cursor": next_cursor}
