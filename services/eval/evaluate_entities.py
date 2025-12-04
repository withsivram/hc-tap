#!/usr/bin/env python3
"""
Evaluate extracted entities against a gold set and persist MICRO F1 into the run manifest.

- Predictions: fixtures/enriched/entities/run=LOCAL/part-000.jsonl
- Gold:        gold/gold_LOCAL.jsonl
- Manifest:    fixtures/runs_LOCAL.json  (adds/overwrites f1_exact_micro, f1_relaxed_micro)

Console output remains identical to the metric printouts.
"""

import json
import os
from collections import Counter, defaultdict

# Default to spacy if env not set, but we try to detect from manifest if possible
EXTRACTOR = os.getenv("EXTRACTOR", "spacy")
PRED_PATH = f"fixtures/enriched/entities/run={EXTRACTOR}/part-000.jsonl"
GOLD_PATH = "gold/gold_LOCAL.jsonl"
MANIFEST_PATH = "fixtures/runs_LOCAL.json"
TYPES = ("PROBLEM", "MEDICATION")


def load_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                # warn but continue
                pass
    return rows


def norm(s):  # normalize text for comparison
    return (s or "").strip().lower()


def iou_span(a, b):
    a0, a1 = a
    b0, b1 = b
    inter = max(0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    return inter / union if union > 0 else 0.0


def matchable(g, p, relaxed=False):
    if g["note_id"] != p["note_id"]:
        return False
    if g["entity_type"] != p["entity_type"]:
        return False
    if norm(g["norm_text"]) != norm(p["norm_text"]):
        return False
    if relaxed:
        return iou_span((g["begin"], g["end"]), (p["begin"], p["end"])) > 0.0
    else:
        return (g["begin"], g["end"]) == (p["begin"], p["end"])


def greedy_match(golds, preds, relaxed=False):
    """Greedy 1:1 matching; returns set of matched pred indices and gold indices."""
    used_pred = set()
    used_gold = set()
    by_key = defaultdict(lambda: {"g": [], "p": []})
    for gi, g in enumerate(golds):
        by_key[(g["note_id"], g["entity_type"])]["g"].append((gi, g))
    for pi, p in enumerate(preds):
        by_key[(p["note_id"], p["entity_type"])]["p"].append((pi, p))
    for key, group in by_key.items():
        g_list = group["g"]
        p_list = group["p"]
        for gi, g in g_list:
            for pi, p in p_list:
                if pi in used_pred:
                    continue
                if matchable(g, p, relaxed=relaxed):
                    used_pred.add(pi)
                    used_gold.add(gi)
                    break
    return used_gold, used_pred


def prf1(tp, fp, fn):
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


def evaluate(mode_label, gold, pred):
    results = {}
    micro = Counter(tp=0, fp=0, fn=0)
    for typ in TYPES:
        g_typ = [g for g in gold if g["entity_type"] == typ]
        p_typ = [p for p in pred if p["entity_type"] == typ]
        used_g, used_p = greedy_match(g_typ, p_typ, relaxed=(mode_label == "RELAXED"))
        tp = len(used_g)
        fp = len(p_typ) - tp
        fn = len(g_typ) - tp
        P, R, F = prf1(tp, fp, fn)
        results[typ] = dict(tp=tp, fp=fp, fn=fn, P=P, R=R, F1=F)
        micro.update(tp=tp, fp=fp, fn=fn)

    Pm, Rm, Fm = prf1(micro["tp"], micro["fp"], micro["fn"])
    macroF = sum(results[t]["F1"] for t in TYPES) / len(TYPES)
    return results, dict(microP=Pm, microR=Rm, microF1=Fm, macroF1=macroF)


def persist_results(
    strict_exact_agg,
    strict_relax_agg,
    inter_exact_agg,
    inter_relax_agg,
    coverage_stats,
    extractor_name,
):
    if not os.path.exists(MANIFEST_PATH):
        return
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return

    if "extractor_metrics" not in manifest:
        manifest["extractor_metrics"] = {}

    metrics = {
        "f1_exact_micro": float(strict_exact_agg["microF1"]),
        "f1_relaxed_micro": float(strict_relax_agg["microF1"]),
        "f1_exact_micro_intersection": float(inter_exact_agg["microF1"]),
        "f1_relaxed_micro_intersection": float(inter_relax_agg["microF1"]),
        "coverage": coverage_stats,
    }

    manifest["extractor_metrics"][extractor_name] = metrics

    # Update top-level legacy fields for backward compatibility if this is the active run
    if manifest.get("extractor") == extractor_name:
        manifest["f1_exact_micro"] = metrics["f1_exact_micro"]
        manifest["f1_relaxed_micro"] = metrics["f1_relaxed_micro"]
        manifest["f1_exact_micro_intersection"] = metrics["f1_exact_micro_intersection"]
        manifest["f1_relaxed_micro_intersection"] = metrics[
            "f1_relaxed_micro_intersection"
        ]
        for k, v in coverage_stats.items():
            manifest[f"coverage_{k}"] = v

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def dedupe(rows):
    seen, out = set(), []
    for o in rows:
        key = (
            o.get("note_id"),
            o.get("entity_type"),
            (o.get("norm_text") or "").strip().lower(),
            o.get("begin"),
            o.get("end"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(o)
    return out


def filter_by_notes(rows, allowed_ids):
    return [r for r in rows if r.get("note_id") in allowed_ids]


def main():
    print(f"[eval] Evaluating run={EXTRACTOR} from {PRED_PATH}")
    preds = load_jsonl(PRED_PATH)
    golds = load_jsonl(GOLD_PATH)

    if not golds:
        print(f"[eval] No gold labels found at {GOLD_PATH}.")
        return
    if not preds:
        print(f"[eval] No predictions found at {PRED_PATH}. Run ETL first.")
        # We continue to clear metrics if needed, or just return
        # But for pipeline robustness, let's just return
        return

    preds = dedupe(preds)
    golds = dedupe(golds)

    # Coverage
    pred_note_ids = {p["note_id"] for p in preds}
    gold_note_ids = {g["note_id"] for g in golds}
    missing_gold_notes = len(gold_note_ids - pred_note_ids)

    coverage_stats = {
        "gold_items": len(golds),
        "pred_items": len(preds),
        "gold_notes": len(gold_note_ids),
        "pred_notes": len(pred_note_ids),
        "gold_outside_pred_notes": missing_gold_notes,
    }

    print(
        f"[coverage] gold={len(golds)} preds={len(preds)} "
        f"notes(gold)={len(gold_note_ids)} notes(pred)={len(pred_note_ids)}"
    )

    # EXACT (Strict)
    exact_per, exact_agg = evaluate("EXACT", golds, preds)
    # RELAXED (Strict)
    relax_per, relax_agg = evaluate("RELAXED", golds, preds)

    # Intersection
    inter_ids = pred_note_ids & gold_note_ids
    g_i = filter_by_notes(golds, inter_ids)
    p_i = filter_by_notes(preds, inter_ids)

    iexact_per, iexact_agg = evaluate("EXACT", g_i, p_i)
    irelax_per, irelax_agg = evaluate("RELAXED", g_i, p_i)

    def pct(x):
        return f"{100*x:.1f}%"

    print("=== EVAL (EXACT spans) ===")
    for typ in TYPES:
        r = exact_per[typ]
        print(
            f"{typ:10s}  TP={r['tp']:2d}  FP={r['fp']:2d}  FN={r['fn']:2d}  P={pct(r['P'])}  R={pct(r['R'])}  F1={pct(r['F1'])}"
        )
    print(f"MICRO F1={pct(exact_agg['microF1'])}")

    # Persist results
    persist_results(
        exact_agg, relax_agg, iexact_agg, irelax_agg, coverage_stats, EXTRACTOR
    )


if __name__ == "__main__":
    main()
