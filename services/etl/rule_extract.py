from __future__ import annotations

import datetime
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Tuple

RUN_ID = os.getenv("RUN_ID", "LOCAL")
NOTES_DIR = Path("fixtures/notes")
ENRICHED_DIR = Path(f"enriched/entities/run={RUN_ID}")
RUN_MANIFEST_PATH = Path("runs/runs_local.json")

PROBLEM_TERMS = [
    "chest tightness",
    "hypertension",
    "diabetes",
    "asthma",
    "nausea",
    "vomiting",
    "rash",
    "fever",
    "headache",
    "back pain",
    "anxiety",
    "depression",
    "insomnia",
    "cough",
    "ough",
]
MEDICATION_TERMS = [
    "metformin",
    "lisinopril",
    "atorvastatin",
    "ibuprofen",
    "naproxen",
    "robitussin",
    "lexapro",
    "hydrocortisone",
    "insulin",
    "reglan",
    "zofran",
    "albuterol",
    "zoloft",
    "ambien",
    "tylenol",
]
DOSAGE_RE = r"(?:\s+\d+\s*(?:mg|mcg|g|ml|units?|iu))?"
DRUG_SUFFIXES = ("pril", "sartan", "statin", "olol", "prazole", "dazole", "cillin")
MED_STOPWORDS = {
    "history",
    "patient",
    "medications",
    "medication",
    "current",
    "daily",
    "placebo",
    "none",
    "allergy",
    "allergies",
    "herb",
    "vitamin",
    "supplement",
    "dose",
    "dosing",
    "prn",
    "home",
    "plan",
    "assessment",
}
PROBLEM_STOPWORDS = {
    "history",
    "patient",
    "family",
    "father",
    "mother",
    "sister",
    "brother",
    "assessment",
    "plan",
    "review",
    "today",
    "daily",
    "taking",
    "weight",
}
NEGATION_RE = re.compile(r"\b(no|denies|without|free of)\b", re.IGNORECASE)
DOSE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?|iu)\b", re.IGNORECASE)
CLINICAL_HINT_RE = re.compile(
    r"(itis|osis|emia|algia|cough|fever|pain|injury|fracture|diabetes|hypertension|asthma|infection|rash|edema|nausea|vomiting|tightness|fatigue)",
    re.IGNORECASE,
)
HIGH_CONF_PROBLEMS = {
    "chest tightness",
    "hypertension",
    "diabetes",
    "asthma",
    "nausea",
    "vomiting",
    "rash",
    "cough",
    "fever",
    "anxiety",
    "depression",
    "insomnia",
    "headache",
    "back pain",
}

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


def utc_iso() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def median_ms(samples: List[float]) -> float:
    if not samples:
        return 0.0
    xs = sorted(samples)
    n = len(xs)
    if n % 2:
        return float(int(round(xs[n // 2] * 1000)))
    return float(int(round((xs[n // 2 - 1] + xs[n // 2]) / 2 * 1000)))


def quantile_ms(samples: List[float], q: float) -> float:
    if not samples:
        return 0.0
    xs = sorted(samples)
    k = max(1, math.ceil(q * len(xs)))
    return float(int(round(xs[k - 1] * 1000)))


def load_notes() -> Iterator[Dict]:
    for path in sorted(NOTES_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as fh:
            yield json.load(fh)


def find_spans(
    text: str, terms: Iterable[str], with_dose: bool = False
) -> Iterator[Tuple[int, int, str, str]]:
    flags = re.IGNORECASE
    for term in terms:
        pattern = (
            rf"\b({re.escape(term)}){DOSAGE_RE}\b"
            if with_dose
            else rf"\b({re.escape(term)})\b"
        )
        for match in re.finditer(pattern, text, flags):
            yield match.start(), match.end(), text[
                match.start() : match.end()
            ], match.group(1).lower()


def guess_section(text: str, begin: int) -> str:
    window = text[max(0, begin - 60) : begin + 60].lower()
    if "assessment" in window or "impression" in window:
        return "Assessment"
    if "started on" in window or "taking " in window:
        return "Plan"
    return "unknown"


def ensure_contract(row: Dict) -> Dict:
    for key in REQUIRED_KEYS:
        row.setdefault(key, None)
    return row


def compute_history_cutoff(text: str) -> int:
    lower = text.lower()
    markers = [
        "past medical history",
        "medical history",
        "pmh",
        "family history",
        "social history",
        "history of present illness",
        "review of systems",
        "ros:",
    ]
    indices = [lower.find(marker) for marker in markers if lower.find(marker) != -1]
    return min(indices) if indices else -1


def has_dose_context(text: str, begin: int, end: int) -> bool:
    window = text[max(0, begin - 60) : min(len(text), end + 60)]
    return bool(DOSE_RE.search(window))


def has_suffix(norm: str) -> bool:
    return any(norm.endswith(suffix) for suffix in DRUG_SUFFIXES)


def is_negated(text: str, begin: int) -> bool:
    window = text[max(0, begin - 40) : begin]
    return bool(NEGATION_RE.search(window))


def has_context_keyword(text: str, begin: int, end: int) -> bool:
    window = text[max(0, begin - 60) : min(len(text), end + 60)].lower()
    keywords = (
        " with ",
        " has ",
        " diagnosed",
        "assessment for",
        " assessment",
        " presents with",
        " presents for",
        " reports ",
        " complains of",
        " symptom",
    )
    return any(keyword in window for keyword in keywords)


def looks_clinical(norm: str) -> bool:
    return bool(CLINICAL_HINT_RE.search(norm))


def in_history_section(text: str, begin: int) -> bool:
    window = text[max(0, begin - 200) : begin].lower()
    history_markers = (
        "past medical history",
        "pmh",
        "medical history",
        "surgical history",
        "family history",
        "social history",
        "history of",
        "hx of",
        "ros:",
        "review of systems",
    )
    return any(marker in window for marker in history_markers)


def should_keep_med(
    span: str, norm: str, text: str, begin: int, end: int, section: str
) -> bool:
    if len(norm) < 4:
        return False
    if norm in MED_STOPWORDS:
        return False
    has_suffix_match = norm in MEDICATION_TERMS or has_suffix(norm)
    if section.lower() != "plan" and not has_dose_context(text, begin, end):
        if not has_suffix_match:
            return False
    if not has_suffix_match and not has_dose_context(text, begin, end):
        return False
    return True


def should_keep_problem(
    span: str,
    norm: str,
    text: str,
    begin: int,
    end: int,
    section: str,
    history_cutoff: int,
) -> bool:
    if len(norm) < 4:
        return False
    if norm in PROBLEM_STOPWORDS:
        return False
    window = text[max(0, begin - 60) : min(len(text), end + 60)].lower()
    if is_negated(text, begin):
        return False
    if "family history" in window or "history of" in window:
        return False
    if history_cutoff != -1 and begin > history_cutoff:
        return False
    if in_history_section(text, begin):
        return False
    if not has_context_keyword(text, begin, end) and section.lower() != "assessment":
        if norm not in HIGH_CONF_PROBLEMS and not looks_clinical(norm):
            return False
    if (
        "mother" in window
        or "father" in window
        or "sister" in window
        or "brother" in window
    ):
        return False
    return True


def extract_for_note(note: Dict) -> List[Dict]:
    note_id = note.get("note_id")
    text = note.get("text", "") or ""
    if not note_id or not text:
        return []

    rows: List[Dict] = []
    seen = set()
    history_cut = compute_history_cutoff(text)

    for begin, end, span, norm in find_spans(text, PROBLEM_TERMS, with_dose=False):
        if begin >= end:
            continue
        norm_clean = norm.strip().lower()
        section = guess_section(text, begin)
        if not should_keep_problem(
            span, norm_clean, text, begin, end, section, history_cut
        ):
            continue
        key = (note_id, "PROBLEM", begin, end, norm_clean)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            dict(
                note_id=note_id,
                run_id=RUN_ID,
                entity_type="PROBLEM",
                text=span.strip(),
                norm_text=norm_clean,
                begin=begin,
                end=end,
                score=0.90,
                section=section,
            )
        )

    for begin, end, span, norm in find_spans(text, MEDICATION_TERMS, with_dose=True):
        if begin >= end:
            continue
        norm_clean = norm.strip().lower()
        section = guess_section(text, begin)
        if not should_keep_med(span, norm_clean, text, begin, end, section):
            continue
        key = (note_id, "MEDICATION", begin, end, norm_clean)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            dict(
                note_id=note_id,
                run_id=RUN_ID,
                entity_type="MEDICATION",
                text=span.strip(),
                norm_text=norm_clean,
                begin=begin,
                end=end,
                score=0.95,
                section=section,
            )
        )

    return rows


def write_entities(rows: Iterable[Dict], sink: Path) -> int:
    written = 0
    with sink.open("a", encoding="utf-8") as fh:
        for row in rows:
            ensure_contract(row)
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
    return written


def update_manifest(processed_notes: int, p50: float, p95: float) -> None:
    record = {
        "run_id": RUN_ID,
        "p50_ms": p50,
        "p95_ms": p95,
        "error_rate": 0.0,
        "processed_notes": processed_notes,
        "ts": utc_iso(),
    }

    RUN_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest: List[Dict] = []

    if RUN_MANIFEST_PATH.exists():
        try:
            with RUN_MANIFEST_PATH.open("r", encoding="utf-8") as fh:
                existing = json.load(fh)
            if isinstance(existing, list):
                manifest = [r for r in existing if str(r.get("run_id")) != str(RUN_ID)]
        except Exception:
            manifest = []

    manifest.append(record)
    with RUN_MANIFEST_PATH.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)


def main() -> None:
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    out_file = ENRICHED_DIR / "entities_local.jsonl"
    out_file.write_text("", encoding="utf-8")

    per_note_durations: List[float] = []
    notes_seen = 0
    entities_written = 0

    for note in load_notes():
        start = time.perf_counter()
        rows = extract_for_note(note)
        if rows:
            entities_written += write_entities(rows, out_file)
        notes_seen += 1 if note.get("note_id") else 0
        per_note_durations.append(time.perf_counter() - start)

    p50 = median_ms(per_note_durations)
    p95 = quantile_ms(per_note_durations, 0.95)
    update_manifest(notes_seen, p50, p95)

    print(f"[rule_extract] notes={notes_seen} entities={entities_written} → {out_file}")
    print(f"[rule_extract] manifest → {RUN_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
