"""
Cloud ETL script for HC-TAP.
Reads raw notes from S3, runs extraction, and writes enriched entities + stats to S3.
"""
import json
import os
import time
import tempfile
from pathlib import Path
from typing import Dict, List

import boto3
from botocore.exceptions import ClientError

# Reuse existing logic
from services.etl.rule_extract import extract_for_note, median_ms, quantile_ms, utc_iso

RAW_BUCKET = os.getenv("RAW_BUCKET")
ENRICHED_BUCKET = os.getenv("ENRICHED_BUCKET")
RUN_ID = os.getenv("RUN_ID", "cloud-latest")

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
    resp = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(resp["Body"].read().decode("utf-8"))

def write_s3_lines(bucket: str, key: str, rows: List[Dict]):
    """Write newline-delimited JSON to S3."""
    if not rows:
        return
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    s3.put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"))

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
            t0 = time.perf_counter()
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
    
    stats = {
        "run_id": RUN_ID,
        "ts": utc_iso(),
        "note_count": processed_count,
        "entity_count": len(all_entities),
        "p50_ms": p50,
        "p95_ms": p95,
        # Placeholder for F1 evaluation (requires Gold set in S3)
        "f1_exact_micro": 0.0, 
        "f1_relaxed_micro": 0.0,
        "status": "success"
    }

    # Write Run Manifest (latest.json)
    manifest_key = "runs/latest.json"
    print(f"Writing manifest to s3://{ENRICHED_BUCKET}/{manifest_key}")
    s3.put_object(
        Bucket=ENRICHED_BUCKET, 
        Key=manifest_key, 
        Body=json.dumps(stats, indent=2).encode("utf-8")
    )
    
    # Also archive specific run manifest
    run_manifest_key = f"runs/{RUN_ID}/manifest.json"
    s3.put_object(
        Bucket=ENRICHED_BUCKET, 
        Key=run_manifest_key, 
        Body=json.dumps(stats, indent=2).encode("utf-8")
    )

    print("Cloud ETL Complete.")

if __name__ == "__main__":
    main()

