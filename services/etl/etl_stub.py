from __future__ import annotations

import json
import datetime as dt
from pathlib import Path

RUN_ID = "LOCAL"  # keep this exact in the stub so Kevin/Suryodaya’s local tools work

NOTES_DIR         = Path("fixtures/notes")             # read only to discover note_ids
SRC_ENTITIES_DIR  = Path("fixtures/entities")          # per-note JSONL input
API_ENRICHED_PATH = Path(f"fixtures/enriched/entities/run={RUN_ID}/part-000.jsonl")
ANA_ENRICHED_DIR  = Path(f"enriched/entities/run={RUN_ID}")
ANA_ENRICHED_PATH = ANA_ENRICHED_DIR / "entities_part1.jsonl"

API_MANIFEST = Path("fixtures/runs_LOCAL.json")  # single object
RUNS_LIST    = Path("runs/runs_local.json")      # list of records
RUNS_BY_ID   = Path("runs") / f"run_{RUN_ID}.json"

REQUIRED_KEYS = [
    "note_id","run_id","entity_type","text","norm_text","begin","end","score","section"
]

def utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def iter_note_ids() -> list[str]:
    ids: list[str] = []
    for p in sorted(NOTES_DIR.glob("*.json")):
        with p.open("r", encoding="utf-8") as f:
            obj = json.load(f)
        nid = obj.get("note_id")
        if nid:
            ids.append(nid)
    return ids

def write_api_manifest(rec: dict) -> None:
    API_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with API_MANIFEST.open("w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2)

def upsert_runs_list(rec: dict) -> None:
    RUNS_LIST.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    if RUNS_LIST.exists():
        try:
            with RUNS_LIST.open("r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, list):
                rows = [r for r in existing if str(r.get("run_id")) != str(rec.get("run_id"))]
        except Exception:
            rows = []
    rows.append({
        "run_id": rec["run_id"],
        "p50_ms": rec.get("duration_ms_p50", 0.0),
        "p95_ms": rec.get("duration_ms_p95", 0.0),
        "error_rate": float(rec.get("errors", 0)) / max(1, int(rec.get("notes_total", 0))),
        "processed_notes": int(rec.get("notes_total", 0)),
    })
    with RUNS_LIST.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)

def main() -> None:
    ts_started = utc_iso()

    API_ENRICHED_PATH.parent.mkdir(parents=True, exist_ok=True)
    ANA_ENRICHED_DIR.mkdir(parents=True, exist_ok=True)

    # start clean
    API_ENRICHED_PATH.write_text("", encoding="utf-8")
    ANA_ENRICHED_PATH.write_text("", encoding="utf-8")

    note_ids = iter_note_ids()
    notes_seen = 0
    entities_written = 0

    with API_ENRICHED_PATH.open("a", encoding="utf-8") as api_sink, \
         ANA_ENRICHED_PATH.open("a", encoding="utf-8") as ana_sink:

        for nid in note_ids:
            notes_seen += 1
            src = SRC_ENTITIES_DIR / f"{nid}.jsonl"
            if not src.exists():
                continue
            with src.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    ent = json.loads(line)
                    ent.setdefault("run_id", RUN_ID)
                    for k in REQUIRED_KEYS:
                        ent.setdefault(k, None)
                    j = json.dumps(ent, ensure_ascii=False) + "\n"
                    api_sink.write(j)
                    ana_sink.write(j)
                    entities_written += 1

    ts_finished = utc_iso()
    record = {
        "run_id": RUN_ID,
        "ts_started": ts_started,
        "ts_finished": ts_finished,
        "notes_total": notes_seen,
        "entities_total": entities_written,
        "errors": 0,
        "duration_ms_p50": 0.0,
        "duration_ms_p95": 0.0,
    }

    write_api_manifest(record)
    upsert_runs_list(record)
    RUNS_BY_ID.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(f"[etl_stub] notes={notes_seen} entities={entities_written} → {API_ENRICHED_PATH}")
    print(f"[etl_stub] mirror → {ANA_ENRICHED_PATH}")
    print(f"[etl_stub] API manifest  → {API_MANIFEST}")
    print(f"[etl_stub] Test manifest → {RUNS_LIST}")

if __name__ == "__main__":
    main()
