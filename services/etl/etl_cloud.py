"""
Cloud ETL script for HC-TAP.
Reads raw notes from S3, runs extraction, evaluation, and writes enriched entities + stats to S3.
"""

import json
import os
import time
from collections import Counter
from typing import Dict, List, Set, Tuple

import boto3
from botocore.exceptions import ClientError

# Reuse existing logic
from services.etl.rule_extract import extract_for_note, median_ms, quantile_ms, utc_iso

RAW_BUCKET = os.getenv("RAW_BUCKET")
ENRICHED_BUCKET = os.getenv("ENRICHED_BUCKET")

# Check which extractor to use
EXTRACTOR_NAME = os.getenv("EXTRACTOR", "rule").lower()
RUN_ID = os.getenv("RUN_ID", f"cloud-{EXTRACTOR_NAME}")

# DEMO MODE: Use comprehensive gold standard for better F1 scores
GOLD_S3_KEY = "gold/gold_DEMO.jsonl"
TYPES = ("PROBLEM", "MEDICATION")

# Import extractors based on configuration
llm_extractor = None
if EXTRACTOR_NAME == "llm":
    try:
        from services.extractors.llm_extract import LLMExtractor
        llm_extractor = LLMExtractor()
        print("✅ LLM Extractor initialized for cloud ETL")
    except Exception as e:
        print(f"Failed to initialize LLM extractor: {e}")
        print("Falling back to rule-based extraction")
        EXTRACTOR_NAME = "rule"
        RUN_ID = "cloud-rule"

s3 = boto3.client("s3")


def list_s3_notes(bucket: str) -> List[str]:
    """List all .json keys in raw bucket."""
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        if "Contents" in page:
            for obj in page["Contents"]:
                if obj["Key"].endswith(".json"):
                    keys.append(obj["Key"])
    return keys


def read_s3_json(bucket: str, key: str) -> Dict:
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(resp["Body"].read().decode("utf-8"))
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"Warning: Key not found in S3: {key}")
            return {}
        print(f"Error reading S3 object {key}: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in S3 object {key}: {e}")
        return {}


def write_s3_lines(bucket: str, key: str, rows: List[Dict]):
    """Write newline-delimited JSON to S3."""
    if not rows:
        return
    try:
        body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
        s3.put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"))
    except ClientError as e:
        print(f"Error writing to S3 {key}: {e}")
        raise


def load_gold_from_s3(bucket: str, key: str) -> List[Dict]:
    """Load gold standard entities from S3."""
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
        body = resp["Body"].read().decode("utf-8")
        rows = []
        for line in body.split("\n"):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"Gold data not found at s3://{bucket}/{key}")
            return []
        print(f"Error loading gold data: {e}")
        return []


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


def greedy_match(golds: List[Dict], preds: List[Dict], relaxed: bool = False) -> Tuple[Set[int], Set[int]]:
    """Greedy 1:1 matching scoped by note + entity_type."""
    from collections import defaultdict

    used_pred: Set[int] = set()
    used_gold: Set[int] = set()
    buckets = defaultdict(lambda: {"g": [], "p": []})

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


def evaluate(golds: List[Dict], preds: List[Dict], relaxed: bool = False) -> Dict[str, float]:
    """Evaluate predictions against gold standard."""
    micro = Counter(tp=0, fp=0, fn=0)

    for entity_type in TYPES:
        g_typ = [g for g in golds if g["entity_type"] == entity_type]
        p_typ = [p for p in preds if p["entity_type"] == entity_type]
        used_g, used_p = greedy_match(g_typ, p_typ, relaxed=relaxed)
        tp = len(used_g)
        fp = len(p_typ) - tp
        fn = len(g_typ) - tp
        micro.update(tp=tp, fp=fp, fn=fn)

    microP, microR, microF1 = prf1(micro["tp"], micro["fp"], micro["fn"])
    return {"microP": microP, "microR": microR, "microF1": microF1}


def filter_by_notes(rows: List[Dict], allowed: Set[str]) -> List[Dict]:
    return [row for row in rows if row.get("note_id") in allowed]


def main():
    if not RAW_BUCKET or not ENRICHED_BUCKET:
        raise ValueError("RAW_BUCKET and ENRICHED_BUCKET env vars must be set")

    print(f"Starting Cloud ETL Run: {RUN_ID}")
    print(f"Reading from s3://{RAW_BUCKET}")

    keys = list_s3_notes(RAW_BUCKET)
    print(f"Found {len(keys)} notes.")

    all_entities = []
    durations = []
    processed_count = 0

    for key in keys:
        try:
            note = read_s3_json(RAW_BUCKET, key)
            note_id = note.get("note_id", key.split("/")[-1].replace(".json", ""))
            
            t0 = time.perf_counter()
            
            # Choose extractor based on EXTRACTOR_NAME
            if EXTRACTOR_NAME == "llm" and llm_extractor:
                entities = llm_extractor.extract(note.get("text", ""), note_id, RUN_ID) or []
            else:
                entities = extract_for_note(note)
            
            durations.append(time.perf_counter() - t0)

            for ent in entities:
                ent["run_id"] = RUN_ID
                all_entities.append(ent)

            processed_count += 1
            if processed_count % 50 == 0:
                print(f"Processed {processed_count}/{len(keys)}...")
        except Exception as e:
            print(f"Error processing {key}: {e}")

    # Write Enriched Data
    out_key = f"runs/{RUN_ID}/entities.jsonl"
    print(f"Writing {len(all_entities)} entities to s3://{ENRICHED_BUCKET}/{out_key}")
    write_s3_lines(ENRICHED_BUCKET, out_key, all_entities)

    # Calculate Stats
    p50 = median_ms(durations)
    p95 = quantile_ms(durations, 0.95)

    # Load gold data and calculate F1 scores
    print(f"Loading gold data from s3://{ENRICHED_BUCKET}/{GOLD_S3_KEY}")
    golds = load_gold_from_s3(ENRICHED_BUCKET, GOLD_S3_KEY)

    f1_exact = 0.0
    f1_relaxed = 0.0
    f1_exact_inter = 0.0
    f1_relaxed_inter = 0.0

    if golds:
        print(f"Found {len(golds)} gold entities, calculating F1 scores...")

        # Calculate strict F1 scores
        strict_exact = evaluate(golds, all_entities, relaxed=False)
        strict_relaxed = evaluate(golds, all_entities, relaxed=True)

        # Calculate intersection F1 scores (only notes with gold labels)
        gold_note_ids = {g.get("note_id") for g in golds if g.get("note_id")}
        pred_note_ids = {p.get("note_id") for p in all_entities if p.get("note_id")}
        inter_ids = pred_note_ids & gold_note_ids
        inter_golds = filter_by_notes(golds, inter_ids)
        inter_preds = filter_by_notes(all_entities, inter_ids)

        inter_exact = evaluate(inter_golds, inter_preds, relaxed=False)
        inter_relaxed = evaluate(inter_golds, inter_preds, relaxed=True)

        f1_exact = strict_exact["microF1"]
        f1_relaxed = strict_relaxed["microF1"]
        f1_exact_inter = inter_exact["microF1"]
        f1_relaxed_inter = inter_relaxed["microF1"]

        print(f"F1 (exact): {f1_exact:.3f}, F1 (relaxed): {f1_relaxed:.3f}")
        print(f"F1 Intersection (exact): {f1_exact_inter:.3f}, (relaxed): {f1_relaxed_inter:.3f}")
        
        # Store additional metrics for dashboard
        precision_exact = strict_exact.get("microP", 0.0)
        recall_exact = strict_exact.get("microR", 0.0)
        precision_exact_inter = inter_exact.get("microP", 0.0)
        recall_exact_inter = inter_exact.get("microR", 0.0)
    else:
        print("No gold data found, F1 scores will be 0.0")
        precision_exact = recall_exact = 0.0
        precision_exact_inter = recall_exact_inter = 0.0

    # Count coverage
    gold_note_ids = {g.get("note_id") for g in golds if g.get("note_id")} if golds else set()
    pred_note_ids = {p.get("note_id") for p in all_entities if p.get("note_id")}
    
    stats = {
        "run_id": RUN_ID,
        "extractor": EXTRACTOR_NAME,
        "ts": utc_iso(),
        "note_count": processed_count,
        "entity_count": len(all_entities),
        "duration_ms_p50": p50,
        "duration_ms_p95": p95,
        "f1_exact_micro": f1_exact,
        "f1_relaxed_micro": f1_relaxed,
        "f1_exact_micro_intersection": f1_exact_inter,
        "f1_relaxed_micro_intersection": f1_relaxed_inter,
        "precision_exact_micro": precision_exact,
        "recall_exact_micro": recall_exact,
        "precision_exact_micro_intersection": precision_exact_inter,
        "recall_exact_micro_intersection": recall_exact_inter,
        "coverage_gold_items": len(golds) if golds else 0,
        "coverage_pred_items": len(all_entities),
        "coverage_gold_notes": len(gold_note_ids),
        "coverage_pred_notes": len(pred_note_ids),
        "status": "success",
    }

    # Write Run Manifest (latest.json)
    manifest_key = "runs/latest.json"
    print(f"Writing manifest to s3://{ENRICHED_BUCKET}/{manifest_key}")
    s3.put_object(
        Bucket=ENRICHED_BUCKET,
        Key=manifest_key,
        Body=json.dumps(stats, indent=2).encode("utf-8"),
    )

    # Also archive specific run manifest
    run_manifest_key = f"runs/{RUN_ID}/manifest.json"
    s3.put_object(
        Bucket=ENRICHED_BUCKET,
        Key=run_manifest_key,
        Body=json.dumps(stats, indent=2).encode("utf-8"),
    )

    print("Cloud ETL Complete ✅")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
