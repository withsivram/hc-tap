#!/usr/bin/env python3
"""
Evaluate LOCAL (rule) extraction against gold labels, emit strict + intersection micro F1,
and persist metrics/coverage into the run manifest atomically.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

DEFAULT_EXTRACTOR = os.getenv("EXTRACTOR", "LOCAL").lower()
DEFAULT_PRED = Path(
    f"fixtures/enriched/entities/run={DEFAULT_EXTRACTOR}/part-000.jsonl"
)
DEFAULT_GOLD = Path("gold/gold_LOCAL.jsonl")
DEFAULT_MANIFEST = Path("fixtures/runs_LOCAL.json")
TYPES: Sequence[str] = ("PROBLEM", "MEDICATION")
HC_DEBUG = os.getenv("HC_TAP_DEBUG", "0") == "1"
CLI_DEBUG = False


def log(message: str, *, debug: bool = False) -> None:
    if debug and not (HC_DEBUG or CLI_DEBUG):
        return
    prefix = "[EVAL]"
    if debug:
        prefix = f"{prefix}[debug]"
    print(f"{prefix} {message}")


def load_jsonl(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                log(f"Skipping malformed JSON line in {path}", debug=True)
    return rows


def normalize_text(value: str) -> str:
    return (value or "").strip().lower()


def spans_overlap(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    return max(0, min(a[1], b[1]) - max(a[0], b[0])) > 0


def matchable(g: Dict, p: Dict, relaxed: bool = False) -> bool:
    if g["note_id"] != p["note_id"]:
        return False
    if g["entity_type"] != p["entity_type"]:
        return False
    if normalize_text(g.get("norm_text")) != normalize_text(p.get("norm_text")):
        return False
    if relaxed:
        return spans_overlap((g["begin"], g["end"]), (p["begin"], p["end"]))
    return (g["begin"], g["end"]) == (p["begin"], p["end"])


def greedy_match(
    golds: List[Dict], preds: List[Dict], relaxed: bool = False
) -> Tuple[Set[int], Set[int]]:
    """Greedy 1:1 matching scoped by note + entity_type."""
    used_pred: Set[int] = set()
    used_gold: Set[int] = set()
    buckets: Dict[Tuple[str, str], Dict[str, List[Tuple[int, Dict]]]] = defaultdict(
        lambda: {"g": [], "p": []}
    )
    for gi, gold in enumerate(golds):
        buckets[(gold["note_id"], gold["entity_type"])]["g"].append((gi, gold))
    for pi, pred in enumerate(preds):
        buckets[(pred["note_id"], pred["entity_type"])]["p"].append((pi, pred))
    for (_, _), group in buckets.items():
        for gi, g in group["g"]:
            for pi, p in group["p"]:
                if pi in used_pred:
                    continue
                if matchable(g, p, relaxed=relaxed):
                    used_pred.add(pi)
                    used_gold.add(gi)
                    break
    return used_gold, used_pred


def prf1(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


def evaluate(
    golds: List[Dict], preds: List[Dict], relaxed: bool = False
) -> Tuple[Dict[str, Dict], Dict[str, float]]:
    per_type: Dict[str, Dict] = {}
    micro = Counter(tp=0, fp=0, fn=0)
    for entity_type in TYPES:
        g_typ = [g for g in golds if g["entity_type"] == entity_type]
        p_typ = [p for p in preds if p["entity_type"] == entity_type]
        used_g, used_p = greedy_match(g_typ, p_typ, relaxed=relaxed)
        tp = len(used_g)
        fp = len(p_typ) - tp
        fn = len(g_typ) - tp
        prec, rec, f1 = prf1(tp, fp, fn)
        per_type[entity_type] = dict(tp=tp, fp=fp, fn=fn, P=prec, R=rec, F1=f1)
        micro.update(tp=tp, fp=fp, fn=fn)
    microP, microR, microF1 = prf1(micro["tp"], micro["fp"], micro["fn"])
    macroF = sum(per_type[t]["F1"] for t in TYPES) / len(TYPES)
    return per_type, dict(microP=microP, microR=microR, microF1=microF1, macroF1=macroF)


def dedupe(rows: List[Dict]) -> List[Dict]:
    seen = set()
    unique: List[Dict] = []
    for row in rows:
        begin = int(row.get("begin", 0) or 0)
        end = int(row.get("end", 0) or 0)
        key = (
            row.get("note_id"),
            row.get("entity_type"),
            begin,
            end,
            normalize_text(row.get("norm_text")),
        )
        if key in seen:
            continue
        seen.add(key)
        row["begin"] = begin
        row["end"] = end
        unique.append(row)
    return unique


def filter_by_notes(rows: List[Dict], allowed: Set[str]) -> List[Dict]:
    if not allowed:
        return []
    return [row for row in rows if row.get("note_id") in allowed]


def atomic_write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), delete=False
    ) as fh:
        json.dump(payload, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
        tmp_name = fh.name
    os.replace(tmp_name, path)


def persist_results(
    manifest_path: Path,
    extractor_name: str,
    strict_exact: Dict | None,
    strict_relaxed: Dict | None,
    inter_exact: Dict | None,
    inter_relaxed: Dict | None,
    coverage: Dict[str, int],
) -> None:
    manifest: Dict = {}
    if manifest_path.exists():
        try:
            with manifest_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                manifest = loaded
        except Exception:
            manifest = {}

    def block(result: Dict | None) -> Dict[str, float | None]:
        if not result:
            return {"micro_precision": None, "micro_recall": None, "micro_f1": None}
        return {
            "micro_precision": result.get("microP"),
            "micro_recall": result.get("microR"),
            "micro_f1": result.get("microF1"),
        }

    metrics = {
        "strict_exact": block(strict_exact),
        "strict_relaxed": block(strict_relaxed),
        "intersection_exact": block(inter_exact),
        "intersection_relaxed": block(inter_relaxed),
        "coverage": coverage,
    }

    manifest.setdefault("extractor_metrics", {})
    manifest["extractor_metrics"][extractor_name] = metrics

    if manifest.get("extractor") == extractor_name or not manifest.get("extractor"):
        manifest["extractor"] = extractor_name
        manifest["f1_exact_micro"] = metrics["strict_exact"]["micro_f1"]
        manifest["f1_relaxed_micro"] = metrics["strict_relaxed"]["micro_f1"]
        manifest["f1_exact_micro_intersection"] = metrics["intersection_exact"][
            "micro_f1"
        ]
        manifest["f1_relaxed_micro_intersection"] = metrics["intersection_relaxed"][
            "micro_f1"
        ]
        manifest["precision_exact_micro"] = metrics["strict_exact"]["micro_precision"]
        manifest["recall_exact_micro"] = metrics["strict_exact"]["micro_recall"]
        manifest["precision_relaxed_micro"] = metrics["strict_relaxed"][
            "micro_precision"
        ]
        manifest["recall_relaxed_micro"] = metrics["strict_relaxed"]["micro_recall"]
        manifest["precision_exact_micro_intersection"] = metrics["intersection_exact"][
            "micro_precision"
        ]
        manifest["recall_exact_micro_intersection"] = metrics["intersection_exact"][
            "micro_recall"
        ]
        manifest["precision_relaxed_micro_intersection"] = metrics[
            "intersection_relaxed"
        ]["micro_precision"]
        manifest["recall_relaxed_micro_intersection"] = metrics["intersection_relaxed"][
            "micro_recall"
        ]
        for key, value in coverage.items():
            manifest[f"coverage_{key}"] = value

    atomic_write_json(manifest_path, manifest)


def format_pct(value: float | None) -> str:
    return f"{100 * value:.1f}%" if value is not None else "N/A"


def build_report_payload(
    extractor: str,
    paths: Dict[str, str],
    coverage: Dict[str, int],
    metrics: Dict[str, Dict | None],
) -> Dict:
    return {
        "extractor": extractor,
        "paths": paths,
        "coverage": coverage,
        "metrics": {
            "strict_exact": metrics["strict_exact"],
            "strict_relaxed": metrics["strict_relaxed"],
            "intersection_exact": metrics["intersection_exact"],
            "intersection_relaxed": metrics["intersection_relaxed"],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate LOCAL rule extractor against gold notes."
    )
    parser.add_argument(
        "--pred", default=str(DEFAULT_PRED), help="Path to predictions JSONL."
    )
    parser.add_argument("--gold", default=str(DEFAULT_GOLD), help="Path to gold JSONL.")
    parser.add_argument(
        "--manifest", default=str(DEFAULT_MANIFEST), help="Run manifest to update."
    )
    parser.add_argument(
        "--extractor", default=DEFAULT_EXTRACTOR, help="Extractor/run identifier."
    )
    parser.add_argument("--report", help="Optional path to write detailed JSON report.")
    parser.add_argument(
        "--debug", action="store_true", help="Print verbose debug details."
    )
    return parser.parse_args()


def main() -> None:
    global CLI_DEBUG
    args = parse_args()
    CLI_DEBUG = args.debug or CLI_DEBUG

    pred_path = Path(args.pred)
    gold_path = Path(args.gold)
    manifest_path = Path(args.manifest)
    extractor = args.extractor.lower()

    log(f"Evaluating run={extractor} predictions={pred_path}", debug=False)

    preds = dedupe(load_jsonl(pred_path))
    golds = dedupe(load_jsonl(gold_path))

    gold_note_ids = {g.get("note_id") for g in golds if g.get("note_id")}
    pred_note_ids = {p.get("note_id") for p in preds if p.get("note_id")}
    coverage_stats = {
        "gold_items": len(golds),
        "pred_items": len(preds),
        "gold_notes": len(gold_note_ids),
        "pred_notes": len(pred_note_ids),
        "gold_outside_pred_notes": len(gold_note_ids - pred_note_ids),
    }

    print(
        "[coverage] "
        f"gold={coverage_stats['gold_items']} "
        f"preds={coverage_stats['pred_items']} "
        f"notes(gold)={coverage_stats['gold_notes']} "
        f"notes(pred)={coverage_stats['pred_notes']} "
        f"gold_outside_pred_notes={coverage_stats['gold_outside_pred_notes']}"
    )

    if not golds:
        log(
            f"No gold labels found at {gold_path}. Skipping metric computation.",
            debug=False,
        )
        persist_results(
            manifest_path, extractor, None, None, None, None, coverage_stats
        )
        if args.report:
            report_payload = build_report_payload(
                extractor,
                {"pred": str(pred_path), "gold": str(gold_path)},
                coverage_stats,
                {
                    "strict_exact": None,
                    "strict_relaxed": None,
                    "intersection_exact": None,
                    "intersection_relaxed": None,
                },
            )
            atomic_write_json(Path(args.report), report_payload)
        return

    if not preds:
        log(f"No predictions found at {pred_path}. Run ETL first.", debug=False)
        persist_results(
            manifest_path, extractor, None, None, None, None, coverage_stats
        )
        return

    strict_exact_per, strict_exact_agg = evaluate(golds, preds, relaxed=False)
    strict_relax_per, strict_relax_agg = evaluate(golds, preds, relaxed=True)

    inter_ids = pred_note_ids & gold_note_ids
    inter_golds = filter_by_notes(golds, inter_ids)
    inter_preds = filter_by_notes(preds, inter_ids)
    inter_exact_per, inter_exact_agg = evaluate(inter_golds, inter_preds, relaxed=False)
    inter_relax_per, inter_relax_agg = evaluate(inter_golds, inter_preds, relaxed=True)

    def log_micro(label: str, agg: Dict[str, float]):
        log(
            f"{label}: P={format_pct(agg['microP'])} "
            f"R={format_pct(agg['microR'])} "
            f"F1={format_pct(agg['microF1'])}",
            debug=False,
        )

    log("=== STRICT (exact spans) ===", debug=False)
    for entity_type in TYPES:
        row = strict_exact_per[entity_type]
        log(
            f"{entity_type:10s} TP={row['tp']:3d} FP={row['fp']:3d} FN={row['fn']:3d} "
            f"P={format_pct(row['P'])} R={format_pct(row['R'])} F1={format_pct(row['F1'])}",
            debug=False,
        )
    log_micro("MICRO (exact)", strict_exact_agg)
    log_micro("MICRO (relaxed)", strict_relax_agg)
    log_micro("INTERSECTION MICRO (exact)", inter_exact_agg)
    log_micro("INTERSECTION MICRO (relaxed)", inter_relax_agg)

    metrics = {
        "strict_exact": strict_exact_agg,
        "strict_relaxed": strict_relax_agg,
        "intersection_exact": inter_exact_agg,
        "intersection_relaxed": inter_relax_agg,
    }

    persist_results(
        manifest_path,
        extractor,
        strict_exact_agg,
        strict_relax_agg,
        inter_exact_agg,
        inter_relax_agg,
        coverage_stats,
    )

    if args.report:
        report_payload = build_report_payload(
            extractor,
            {"pred": str(pred_path), "gold": str(gold_path)},
            coverage_stats,
            metrics,
        )
        atomic_write_json(Path(args.report), report_payload)


if __name__ == "__main__":
    main()
