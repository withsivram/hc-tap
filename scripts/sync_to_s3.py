#!/usr/bin/env python3
"""
Sync local notes to S3 raw bucket.
"""
import os
from pathlib import Path

import boto3

NOTES_DIR = Path("fixtures/notes")
BUCKET_NAME = os.getenv("RAW_BUCKET", "hc-tap-raw-notes")


def sync():
    if not NOTES_DIR.exists():
        print(f"Notes directory {NOTES_DIR} does not exist.")
        return

    s3 = boto3.client("s3")

    # Check if bucket exists
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
    except Exception as e:
        print(f"Error: Bucket '{BUCKET_NAME}' does not exist or is not accessible.")
        print(f"Details: {e}")
        print(f"Create bucket with: aws s3 mb s3://{BUCKET_NAME}")
        return

    # Simple sync: upload all files
    # For production, use "aws s3 sync" CLI or check ETags
    print(f"Syncing {NOTES_DIR} to s3://{BUCKET_NAME}...")

    count = 0
    for path in NOTES_DIR.glob("*.json"):
        key = path.name
        print(f"Uploading {key}...", end="\r")
        try:
            s3.upload_file(str(path), BUCKET_NAME, key)
            count += 1
        except Exception as e:
            print(f"\nError uploading {key}: {e}")

    print(f"\nSynced {count} files.")


if __name__ == "__main__":
    sync()
