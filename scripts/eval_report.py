#!/usr/bin/env python3
"""
Provide a per-note relaxed evaluation report to surface FP-heavy notes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set, Tuple

GOLD_PATH = Path("gold/gold_LOCAL.jsonl")
PRED_PATH = Path("fixtures/enriched/entities/run=LOCAL/part-000.jsonl")
TYPES = ("PROBLEM", "MEDICATION")


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
                continue
    return rows


def normalize_text(value: str) -> str:
    return (value or "").strip().lower()


def spans_overlap(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    return max(0, min(a[1], b[1]) - max(a[0], b[0])) > 0


def dedupe(rows: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
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


def greedy_match(golds: List[Dict], preds: List[Dict]) -> Tuple[Set[int], Set[int]]:
    matched_gold: Set[int] = set()
    matched_pred: Set[int] = set()
    for gi, g in enumerate(golds):
        for pi, p in enumerate(preds):
            if pi in matched_pred or g["entity_type"] != p["entity_type"]:
                continue
            if not spans_overlap((g["begin"], g["end"]), (p["begin"], p["end"])):
                continue
            if normalize_text(g.get("norm_text")) != normalize_text(p.get("norm_text")):
                continue
            matched_gold.add(gi)
            matched_pred.add(pi)
            break
    return matched_gold, matched_pred


def per_note_report() -> None:
    preds = dedupe(load_jsonl(PRED_PATH))
    golds = dedupe(load_jsonl(GOLD_PATH))

    if not preds or not golds:
        print("[eval-report] Missing predictions or gold labels.")
        return

    gold_by_note: Dict[str, List[Dict]] = {}
    pred_by_note: Dict[str, List[Dict]] = {}
    for row in golds:
        gold_by_note.setdefault(row["note_id"], []).append(row)
    for row in preds:
        pred_by_note.setdefault(row["note_id"], []).append(row)

    intersection = sorted(set(gold_by_note.keys()) & set(pred_by_note.keys()))
    if not intersection:
        print("[eval-report] No overlapping notes between gold and predictions.")
        return

    note_stats = []
    for note_id in intersection:
        g_list = gold_by_note[note_id]
        p_list = pred_by_note[note_id]
        matched_g, matched_p = greedy_match(g_list, p_list)
        fps = [p_list[i] for i in range(len(p_list)) if i not in matched_p]
        fns = [g_list[i] for i in range(len(g_list)) if i not in matched_g]
        tps = len(matched_g)
        note_stats.append(
            {
                "note_id": note_id,
                "tp": tps,
                "fp": fps,
                "fn": fns,
            }
        )

    top_fp = sorted(note_stats, key=lambda x: len(x["fp"]), reverse=True)[:5]
    print("[eval-report] Top FP-heavy notes")
    for entry in top_fp:
        note_id = entry["note_id"]
        fp_count = len(entry["fp"])
        fn_count = len(entry["fn"])
        tp_count = entry["tp"]
        print(f"- {note_id}: FP={fp_count} TP={tp_count} FN={fn_count}")
        for fp in entry["fp"][:5]:
            text = (fp.get("text") or "").replace("\n", " ")
            span = f"{fp.get('begin')}–{fp.get('end')}"
            print(f"    [ ] {fp.get('entity_type')} :: {text} ({span})")


def main() -> None:
    per_note_report()


if __name__ == "__main__":
    main()
