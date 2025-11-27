from __future__ import annotations

import os, re, json, time, math, hashlib, random
import datetime as dt
from pathlib import Path
from typing import Iterable, Iterator, List, Dict, Tuple

# ---- Config (keep these stable so API/Analytics keep working) ----
RUN_ID = os.getenv("RUN_ID") or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
NOTES_DIR = Path("fixtures/notes")

# API expects this exact file:
API_ENRICHED_PATH = Path(f"fixtures/enriched/entities/run={RUN_ID}/part-000.jsonl")

# Analytics reads from here (any filename under this folder is OK):
ANALYTICS_ENRICHED_DIR = Path(f"enriched/entities/run={RUN_ID}")
ANALYTICS_ENRICHED_PATH = ANALYTICS_ENRICHED_DIR / "entities_local.jsonl"

# Manifests (API returns the single-object file; analytics/test reads the list file):
API_MANIFEST = Path("fixtures/runs_LOCAL.json")
RUNS_LIST   = Path("runs/runs_local.json")
RUNS_BY_ID  = Path("runs") / f"run_{RUN_ID}.json"  # one-per-run breadcrumb

# Local state for idempotency
CHECKSUM_DIR = Path("fixtures/checksums")

# ---- Tiny rule set (placeholder for Comprehend Medical later) ----
PROBLEM_TERMS    = ["hypertension", "chest tightness", "diabetes", "asthma"]
MEDICATION_TERMS = ["metformin", "lisinopril", "atorvastatin", "ibuprofen"]
DOSAGE_RE        = r"(?:\s+\d+\s*(?:mg|mcg|g))?"

REQUIRED_KEYS = [
    "note_id","run_id","entity_type","text","norm_text","begin","end","score","section"
]

# ---- Helpers ----
def utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def median_ms(xs: List[float]) -> float:
    if not xs: return 0.0
    s = sorted(xs); n = len(s)
    if n % 2: return float(int(round(s[n//2] * 1000)))
    return float(int(round((s[n//2 - 1] + s[n//2]) / 2 * 1000)))

def quantile_ms(xs: List[float], q: float) -> float:
    if not xs: return 0.0
    s = sorted(xs); k = max(1, math.ceil(q * len(s)))
    return float(int(round(s[k - 1] * 1000)))

def sha256_text(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()

def read_json_retry(path: Path, retries: int = 2) -> dict | None:
    delay = 0.02
    for attempt in range(retries + 1):
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            if attempt == retries:
                return None
            time.sleep(delay)
            delay *= 2 * (1 + 0.25 * random.random())
    return None

def iter_note_files() -> List[Path]:
    return sorted(NOTES_DIR.glob("*.json"))

def chunked(items: List[Path], size: int) -> Iterator[List[Path]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]

def find_spans(text: str, terms: Iterable[str], with_dose: bool = False) -> Iterator[Tuple[int,int,str,str]]:
    flags = re.IGNORECASE
    for term in terms:
        pat = rf"\b({re.escape(term)}){DOSAGE_RE}\b" if with_dose else rf"\b({re.escape(term)})\b"
        for m in re.finditer(pat, text, flags):
            yield m.start(), m.end(), text[m.start():m.end()], m.group(1).lower()

def guess_section(text: str, begin: int) -> str:
    window = text[max(0, begin-60): begin+60].lower()
    if "assessment" in window or "impression" in window: return "Assessment"
    if "started on" in window or "taking " in window:     return "Plan"
    return "unknown"

def ensure_contract(row: Dict) -> Dict:
    for k in REQUIRED_KEYS:
        row.setdefault(k, None)
    return row

# ---- Writers ----
def write_api_manifest(manifest: Dict) -> None:
    API_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with API_MANIFEST.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

def upsert_runs_list(record: Dict) -> None:
    RUNS_LIST.parent.mkdir(parents=True, exist_ok=True)
    rows: List[Dict] = []
    if RUNS_LIST.exists():
        try:
            with RUNS_LIST.open("r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, list):
                rows = [r for r in existing if str(r.get("run_id")) != str(record.get("run_id"))]
        except Exception:
            rows = []
    rows.append({
        "run_id": record["run_id"],
        "p50_ms": record.get("duration_ms_p50", 0.0),
        "p95_ms": record.get("duration_ms_p95", 0.0),
        "error_rate": float(record.get("errors", 0)) / max(1, int(record.get("notes_total", 0))),
        "processed_notes": int(record.get("notes_total", 0)),
    })
    with RUNS_LIST.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)

def write_run_breadcrumb(record: Dict) -> None:
    RUNS_BY_ID.parent.mkdir(parents=True, exist_ok=True)
    with RUNS_BY_ID.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

# ---- Core ----
def extract_entities(note: Dict) -> List[Dict]:
    nid  = note.get("note_id")
    text = note.get("text", "") or ""
    if not nid or not text:
        return []
    rows: List[Dict] = []
    for b,e,span,norm in find_spans(text, PROBLEM_TERMS, with_dose=False):
        rows.append(dict(
            note_id=nid, run_id=RUN_ID, entity_type="PROBLEM",
            text=span, norm_text=norm, begin=b, end=e, score=0.90, section=guess_section(text, b)
        ))
    for b,e,span,norm in find_spans(text, MEDICATION_TERMS, with_dose=True):
        rows.append(dict(
            note_id=nid, run_id=RUN_ID, entity_type="MEDICATION",
            text=span, norm_text=norm, begin=b, end=e, score=0.95, section=guess_section(text, b)
        ))
    return rows

def main() -> None:
    ts_started = utc_iso()

    API_ENRICHED_PATH.parent.mkdir(parents=True, exist_ok=True)
    ANALYTICS_ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    CHECKSUM_DIR.mkdir(parents=True, exist_ok=True)

    # start clean
    API_ENRICHED_PATH.write_text("", encoding="utf-8")
    ANALYTICS_ENRICHED_PATH.write_text("", encoding="utf-8")

    notes = iter_note_files()
    per_note_ms: List[float] = []
    notes_seen = 0
    entities_total = 0
    errors = 0
    skipped = 0

    with API_ENRICHED_PATH.open("a", encoding="utf-8") as api_sink, \
         ANALYTICS_ENRICHED_PATH.open("a", encoding="utf-8") as ana_sink:

        for batch in chunked(notes, size=100):
            for p in batch:
                note = read_json_retry(p, retries=2)
                if note is None:
                    errors += 1
                    continue

                nid  = note.get("note_id")
                text = note.get("text", "")
                if not nid or not text:
                    errors += 1
                    continue

                # idempotency
                new_hash = sha256_text(text)
                cs_path = CHECKSUM_DIR / f"{nid}.sha256"
                old_hash = cs_path.read_text(encoding="utf-8").strip() if cs_path.exists() else ""
                if old_hash == new_hash:
                    skipped += 1
                    notes_seen += 1
                    continue

                t0 = time.perf_counter()
                rows = extract_entities(note)
                for r in rows:
                    ensure_contract(r)
                    line = json.dumps(r, ensure_ascii=False) + "\n"
                    api_sink.write(line)
                    ana_sink.write(line)
                dt_ms = (time.perf_counter() - t0) * 1000.0
                per_note_ms.append(dt_ms / 1000.0)  # store seconds for helpers

                entities_total += len(rows)
                notes_seen += 1
                cs_path.write_text(new_hash, encoding="utf-8")

    ts_finished = utc_iso()
    p50 = median_ms(per_note_ms)
    p95 = quantile_ms(per_note_ms, 0.95)

    record = {
        "run_id": RUN_ID,
        "ts_started": ts_started,
        "ts_finished": ts_finished,
        "notes_total": notes_seen,
        "entities_total": entities_total,
        "skipped": skipped,
        "errors": errors,
        "duration_ms_p50": p50,
        "duration_ms_p95": p95,
        # F1s are added later by evaluator
    }

    # write manifests in both shapes
    write_api_manifest(record)     # fixtures/runs_LOCAL.json (single object)
    upsert_runs_list(record)       # runs/runs_local.json     (list of records)
    write_run_breadcrumb(record)   # runs/run_<RUN_ID>.json

    print(f"[rule_extract] notes={notes_seen}  entities={entities_total}  skipped={skipped}  errors={errors}")
    print(f"[rule_extract] API file  → {API_ENRICHED_PATH}")
    print(f"[rule_extract] Mirror    → {ANALYTICS_ENRICHED_PATH}")
    print(f"[rule_extract] API manifest  → {API_MANIFEST}")
    print(f"[rule_extract] Runs list     → {RUNS_LIST}")
    print(f"[rule_extract] Run record    → {RUNS_BY_ID}")

if __name__ == "__main__":
    main()
