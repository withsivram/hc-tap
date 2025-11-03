#!/usr/bin/env python3
"""
Evaluate extracted entities against a gold set and persist MICRO F1 into the run manifest.

- Predictions: fixtures/enriched/entities/run=LOCAL/part-000.jsonl
- Gold:        gold/gold_LOCAL.jsonl
- Manifest:    fixtures/runs_LOCAL.json  (adds/overwrites f1_exact_micro, f1_relaxed_micro)

Console output remains identical to the metric printouts.
"""

import json, os, math
from collections import defaultdict, Counter

PRED_PATH = "fixtures/enriched/entities/run=LOCAL/part-000.jsonl"
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
            except json.JSONDecodeError as e:
                raise SystemExit(f"[read] bad JSON in {path}:{ln}: {e}")
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
        by_key[(g["note_id"], g["entity_type"]) ]["g"].append((gi, g))
    for pi, p in enumerate(preds):
        by_key[(p["note_id"], p["entity_type"]) ]["p"].append((pi, p))
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
    rec  = tp / (tp + fn) if (tp + fn) else 0.0
    f1   = 2*prec*rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1

def evaluate(mode_label, gold, pred):
    results = {}
    micro = Counter(tp=0, fp=0, fn=0)
    for typ in TYPES:
        g_typ = [g for g in gold if g["entity_type"] == typ]
        p_typ = [p for p in pred if p["entity_type"] == typ]
        used_g, used_p = greedy_match(g_typ, p_typ, relaxed=(mode_label=="RELAXED"))
        tp = len(used_g)
        fp = len(p_typ) - tp
        fn = len(g_typ) - tp
        P, R, F = prf1(tp, fp, fn)
        results[typ] = dict(tp=tp, fp=fp, fn=fn, P=P, R=R, F1=F)
        micro.update(tp=tp, fp=fp, fn=fn)

    Pm, Rm, Fm = prf1(micro["tp"], micro["fp"], micro["fn"])
    macroF = sum(results[t]["F1"] for t in TYPES) / len(TYPES)
    return results, dict(microP=Pm, microR=Rm, microF1=Fm, macroF1=macroF)

def persist_micro_f1(exact_micro_f1, relaxed_micro_f1):
    if not os.path.exists(MANIFEST_PATH):
        # No manifest yet; silently skip per the acceptance criteria
        return
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        # If corrupted, don't crash eval; just skip persisting
        return
    manifest["f1_exact_micro"] = float(exact_micro_f1)
    manifest["f1_relaxed_micro"] = float(relaxed_micro_f1)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

def dedupe(rows):
    """Remove duplicate entities based on (note_id, type, norm_text, begin, end)."""
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

def main():
    preds = load_jsonl(PRED_PATH)
    golds = load_jsonl(GOLD_PATH)
    if not golds:
        print(f"[eval] No gold labels found at {GOLD_PATH}. Add labels first.")
        return
    if not preds:
        print(f"[eval] No predictions found at {PRED_PATH}. Run ETL first.")
        return

    # Dedupe predictions and gold before scoring
    preds = dedupe(preds)
    golds = dedupe(golds)

    if os.getenv("DEBUG_EVAL") == "1":
        from collections import Counter
        print(f"[debug] preds={len(preds)} golds={len(golds)}")
        print("[debug] pred types:", Counter([p["entity_type"] for p in preds]))
        print("[debug] gold types:", Counter([g["entity_type"] for g in golds]))

    # EXACT
    exact_per, exact_agg = evaluate("EXACT", golds, preds)
    # RELAXED (any-overlap)
    relax_per, relax_agg = evaluate("RELAXED", golds, preds)

    def pct(x): return f"{100*x:.1f}%"

    print("=== EVAL (EXACT spans) ===")
    for typ in TYPES:
        r = exact_per[typ]
        print(f"{typ:10s}  TP={r['tp']:2d}  FP={r['fp']:2d}  FN={r['fn']:2d}  P={pct(r['P'])}  R={pct(r['R'])}  F1={pct(r['F1'])}")
    print(f"MICRO F1={pct(exact_agg['microF1'])}   MACRO F1={pct(exact_agg['macroF1'])}")

    print("\n=== EVAL (RELAXED overlap) ===")
    for typ in TYPES:
        r = relax_per[typ]
        print(f"{typ:10s}  TP={r['tp']:2d}  FP={r['fp']:2d}  FN={r['fn']:2d}  P={pct(r['P'])}  R={pct(r['R'])}  F1={pct(r['F1'])}")
    print(f"MICRO F1={pct(relax_agg['microF1'])}   MACRO F1={pct(relax_agg['macroF1'])}")

    # Persist MICRO F1s to manifest (no extra console prints)
    persist_micro_f1(exact_agg["microF1"], relax_agg["microF1"])

    except Exception as e:
        print(f"\nWarning: Could not update {manifest_path}: {e}")
        print("Metrics were computed but not persisted.")

if __name__ == "__main__":
    main()