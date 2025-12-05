from __future__ import annotations

import datetime
import json
import math
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Tuple

from services.etl.sections import detect_sections, in_section

PROFILE = os.getenv("RULES_PROFILE", "default").lower()
PROFILE_STRICT = PROFILE == "strict"
PROFILE_STRICT_LITE = PROFILE == "strict-lite"
PROFILE_STRICTISH = PROFILE_STRICT or PROFILE_STRICT_LITE
HC_DEBUG = os.getenv("HC_TAP_DEBUG", "0") == "1"
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
DOSE_TOKEN_RE = re.compile(
    r"(?:mg|mcg|g|ml|units?|iu|tab|tabs|caps?|q\d?h|bid|tid|qhs)", re.IGNORECASE
)
TOKEN_RE = re.compile(r"[A-Za-z']+")
POSITIVE_CONTEXT_TOKENS = {
    "has",
    "with",
    "presents",
    "reports",
    "diagnosed",
    "assessment",
    "shows",
    "exhibits",
    "complains",
    "complaint",
}
ROS_GENERIC_SUPPRESS = {"vomiting", "fever", "headache", "nausea", "dizziness"}
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

HISTORY_SECTIONS = {
    "past medical history",
    "medical history",
    "family history",
    "social history",
}
ROS_SECTIONS = {"review of systems", "ros"}
HPI_SECTIONS = {"history of present illness"}
ASSESS_SECTIONS = {"assessment", "impression", "plan"}
MED_SECTIONS = {"medications"}

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


def section_for_span(
    sections: List[Tuple[str, int, int]], text: str, begin: int
) -> str:
    for name, start, end in sections:
        if start <= begin < end:
            return name
    return guess_section(text, begin).lower()


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


def tokenize(text: str) -> List[Tuple[str, int, int]]:
    return [
        (match.group(0).lower(), match.start(), match.end())
        for match in TOKEN_RE.finditer(text)
    ]


def tokens_near(
    tokens: List[Tuple[str, int, int]], begin: int, end: int, window: int
) -> List[str]:
    if not tokens:
        return []
    idx = 0
    for i, (_, start, stop) in enumerate(tokens):
        if start <= begin < stop or (start >= begin and start < end):
            idx = i
            break
        if start > begin:
            idx = i
            break
    start_idx = max(0, idx - window)
    end_idx = min(len(tokens), idx + window + 1)
    return [tokens[i][0] for i in range(start_idx, end_idx)]


def has_positive_context(
    tokens: List[Tuple[str, int, int]], begin: int, end: int
) -> bool:
    window_tokens = tokens_near(tokens, begin, end, 5)
    return any(token in POSITIVE_CONTEXT_TOKENS for token in window_tokens)


def has_dose_tokens(tokens: List[Tuple[str, int, int]], begin: int, end: int) -> bool:
    window_tokens = tokens_near(tokens, begin, end, 3)
    return any(DOSE_TOKEN_RE.fullmatch(token) for token in window_tokens)


def should_keep_med(
    span: str,
    norm: str,
    text: str,
    begin: int,
    end: int,
    section_name: str,
) -> bool:
    if len(norm) < 4:
        return False
    if norm in MED_STOPWORDS:
        return False
    has_suffix_match = norm in MEDICATION_TERMS or has_suffix(norm)
    has_dose = has_dose_context(text, begin, end)
    section = (section_name or "unknown").lower()
    if PROFILE_STRICTISH:
        in_preferred_section = section in MED_SECTIONS or section in ASSESS_SECTIONS
        if not in_preferred_section and not has_dose and not has_suffix_match:
            return False
    if not has_suffix_match and not has_dose:
        return False
    return True


def should_keep_problem(
    span: str,
    norm: str,
    text: str,
    begin: int,
    end: int,
    section_name: str,
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
    section = (section_name or "unknown").lower()
    lacks_context = not has_context_keyword(text, begin, end)
    if PROFILE_STRICT:
        if history_cutoff != -1 and begin > history_cutoff:
            return False
        if section in HISTORY_SECTIONS and lacks_context:
            return False
        if section in ROS_SECTIONS and lacks_context:
            return False
        if section in HPI_SECTIONS and lacks_context:
            return False
    elif PROFILE_STRICT_LITE:
        if history_cutoff != -1 and begin > history_cutoff and norm not in HIGH_CONF_PROBLEMS:
            return False
        if (
            section in HISTORY_SECTIONS
            and lacks_context
            and norm not in HIGH_CONF_PROBLEMS
            and not looks_clinical(norm)
        ):
            return False
        if (
            section in ROS_SECTIONS
            and lacks_context
            and norm in ROS_GENERIC_SUPPRESS
        ):
            return False
    if lacks_context and section not in ASSESS_SECTIONS:
        if PROFILE_STRICT:
            return False
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
    sections = detect_sections(text)
    tokens = tokenize(text)
    debug_counts = defaultdict(int) if PROFILE_STRICT and HC_DEBUG else None

    for begin, end, span, norm in find_spans(text, PROBLEM_TERMS, with_dose=False):
        if begin >= end:
            continue
        norm_clean = norm.strip().lower()
        section = section_for_span(sections, text, begin)
        if PROFILE_STRICT and debug_counts is not None:
            debug_counts[f"problem_candidates_{section}"] += 1
        positive_context = has_positive_context(tokens, begin, end) or (
            section in ASSESS_SECTIONS
        )
        suppress = False
        if PROFILE_STRICT:
            if in_section(begin, end, sections, ROS_SECTIONS) and not positive_context:
                if debug_counts is not None:
                    debug_counts["suppressed_by_ros"] += 1
                suppress = True
            elif (
                in_section(begin, end, sections, HISTORY_SECTIONS)
                and not positive_context
            ):
                if debug_counts is not None:
                    debug_counts["suppressed_by_pmh"] += 1
                suppress = True
            elif (
                norm_clean in ROS_GENERIC_SUPPRESS
                and in_section(begin, end, sections, ROS_SECTIONS)
                and not positive_context
            ):
                if debug_counts is not None:
                    debug_counts["suppressed_ros_generic"] += 1
                suppress = True
        elif PROFILE_STRICT_LITE:
            if (
                norm_clean in ROS_GENERIC_SUPPRESS
                and in_section(begin, end, sections, ROS_SECTIONS)
                and not positive_context
            ):
                suppress = True
        if suppress:
            continue
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
        section = section_for_span(sections, text, begin)
        if PROFILE_STRICTISH:
            dose_ok = has_dose_tokens(tokens, begin, end)
            in_med = in_section(begin, end, sections, MED_SECTIONS)
            in_plan = in_section(begin, end, sections, {"plan"})
            if in_med and debug_counts is not None:
                debug_counts["allowed_in_meds_section"] += 1
            if not (dose_ok or in_med or in_plan):
                if debug_counts is not None:
                    debug_counts["suppressed_no_dose"] += 1
                continue
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

    if PROFILE == "strict" and debug_counts:
        for key, value in sorted(debug_counts.items()):
            print(f"[ETL|STRICT] {key}={value}")
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
