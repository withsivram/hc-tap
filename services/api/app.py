import json
import logging
import os
import time

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from services.api.settings import settings
from services.etl.preprocess import normalize_text
from services.etl.rule_extract import extract_for_note

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

APP_RUN_ID = settings.APP_RUN_ID
NOTES_DIR = settings.NOTES_DIR
ENRICHED_FILE = f"{settings.ENRICHED_DIR}/run={APP_RUN_ID}/part-000.jsonl"
RUN_MANIFEST = settings.RUN_MANIFEST
ENRICHED_BUCKET = os.getenv("ENRICHED_BUCKET")

app = FastAPI(title="HC-TAP API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache for data with timestamp
_data_cache = {
    "notes": {},
    "entities": ([], {}),
    "last_reload": None,
    "cache_ttl": 30,  # 30 seconds TTL
}


@app.get("/")
def root():
    return {"status": "ok", "service": "hc-tap-api"}


@app.get("/health")
def health():
    """Enhanced health check with system status."""
    health_status = {"ok": True, "status": "healthy", "checks": {}}

    # Check if notes directory exists
    try:
        if os.path.exists(NOTES_DIR):
            note_count = len([f for f in os.listdir(NOTES_DIR) if f.endswith(".json")])
            health_status["checks"]["notes_dir"] = {"ok": True, "count": note_count}
        else:
            health_status["checks"]["notes_dir"] = {
                "ok": False,
                "error": "Directory not found",
            }
            health_status["ok"] = False
    except Exception as e:
        health_status["checks"]["notes_dir"] = {"ok": False, "error": str(e)}
        health_status["ok"] = False

    # Check if enriched file exists
    try:
        if os.path.exists(ENRICHED_FILE):
            health_status["checks"]["enriched_file"] = {"ok": True}
        else:
            health_status["checks"]["enriched_file"] = {
                "ok": False,
                "warning": "File not found",
            }
    except Exception as e:
        health_status["checks"]["enriched_file"] = {"ok": False, "error": str(e)}

    # Check manifest
    try:
        if os.path.exists(RUN_MANIFEST):
            health_status["checks"]["manifest"] = {"ok": True}
        else:
            health_status["checks"]["manifest"] = {
                "ok": False,
                "warning": "File not found",
            }
    except Exception as e:
        health_status["checks"]["manifest"] = {"ok": False, "error": str(e)}

    if not health_status["ok"]:
        health_status["status"] = "degraded"

    return health_status


@app.get("/config")
def config():
    return {
        "RUN_ID": APP_RUN_ID,
        "NOTES_DIR": NOTES_DIR,
        "ENRICHED_FILE": ENRICHED_FILE,
        "RUN_MANIFEST": RUN_MANIFEST,
        "ENRICHED_BUCKET": ENRICHED_BUCKET,
    }


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
        except Exception as e:
            logger.warning(f"Failed to load note {name}: {e}")
    return notes


def load_entities_index():
    """Return (all_entities_list, by_note_id_dict)."""
    all_ents = []
    by_note = {}

    # Target specific run if it exists, otherwise empty
    # Ideally this should be dynamic based on query param or fallback to 'spacy' if LOCAL missing
    target_file = ENRICHED_FILE

    if not os.path.exists(target_file):
        return all_ents, by_note

    with open(target_file, "r", encoding="utf-8") as f:
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
    """Reload data with caching."""
    global NOTES, ALL_ENTS, ENTS_BY_NOTE

    now = time.time()
    if (
        _data_cache["last_reload"] is not None
        and now - _data_cache["last_reload"] < _data_cache["cache_ttl"]
    ):
        # Use cached data
        NOTES = _data_cache["notes"]
        ALL_ENTS, ENTS_BY_NOTE = _data_cache["entities"]
        return

    try:
        NOTES = load_notes()
        ALL_ENTS, ENTS_BY_NOTE = load_entities_index()

        # Update cache
        _data_cache["notes"] = NOTES
        _data_cache["entities"] = (ALL_ENTS, ENTS_BY_NOTE)
        _data_cache["last_reload"] = now
    except Exception as e:
        logger.warning(f"Error reloading data: {e}")
        # Use cached data if available
        if _data_cache["notes"]:
            NOTES = _data_cache["notes"]
            ALL_ENTS, ENTS_BY_NOTE = _data_cache["entities"]


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

    if manifest.get("run_id") != run_id:
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "message": "run not found"},
        )

    return {
        "run_id": manifest.get("run_id"),
        "note_count": manifest.get("note_count", manifest.get("notes_total")),
        "entity_count": manifest.get("entity_count", manifest.get("entities_total")),
        "f1_exact_micro": manifest.get("f1_exact_micro"),
        "f1_relaxed_micro": manifest.get("f1_relaxed_micro"),
        "ts": manifest.get("ts", manifest.get("ts_finished")),
    }


@app.get("/stats/latest")
def get_latest_stats():
    """Fetch latest run stats from S3 if configured, else local."""
    if ENRICHED_BUCKET:
        s3 = boto3.client("s3")
        try:
            resp = s3.get_object(Bucket=ENRICHED_BUCKET, Key="runs/latest.json")
            data = json.loads(resp["Body"].read().decode("utf-8"))
            return data
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return JSONResponse(
                    status_code=404,
                    content={"error": "not_found", "message": "No cloud run found"},
                )
            return JSONResponse(
                status_code=500,
                content={"error": "s3_error", "message": str(e)},
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": "s3_error", "message": str(e)},
            )

    # Fallback to local for non-cloud envs
    return get_run_stats("LOCAL")


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
        # scan enriched over norm_text substring (norm_text is already lowercase)
        items = [e for e in items if (e.get("norm_text") and ql in e.get("norm_text"))]

    return items[:limit]


class ExtractRequest(BaseModel):
    text: str
    note_id: str | None = None

    def validate_text(self):
        """Validate text field"""
        if not self.text or not self.text.strip():
            raise ValueError("Text cannot be empty")
        if len(self.text) > 100000:  # 100KB limit
            raise ValueError("Text too large (max 100KB)")
        return self.text


@app.post("/extract")
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute
def extract_text(request: Request, extract_request: ExtractRequest):
    try:
        text = extract_request.validate_text()
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"error": "bad_request", "message": str(e)},
        )

    text = normalize_text(text)
    note_payload = {
        "note_id": extract_request.note_id or "demo",
        "text": text,
    }
    entities = extract_for_note(note_payload)
    return {"entities": entities}
