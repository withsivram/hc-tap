import os
import boto3
from pathlib import Path

# Configuration
AWS_REGION = "us-east-1"
AWS_ACCOUNT_ID = "099200121087"
RAW_BUCKET = f"hc-tap-raw-{AWS_ACCOUNT_ID}-{AWS_REGION}-dev"
LOCAL_DIR = Path("fixtures/notes")

def sync_to_s3():
    """Uploads local fixtures/notes/ to the raw S3 bucket."""
    print(f"Syncing {LOCAL_DIR} to s3://{RAW_BUCKET}...")
    
    s3 = boto3.client("s3", region_name=AWS_REGION)
    
    # Check if bucket exists
    try:
        s3.head_bucket(Bucket=RAW_BUCKET)
    except Exception as e:
        print(f"Error: Bucket {RAW_BUCKET} not found or not accessible. {e}")
        return

    if not LOCAL_DIR.exists():
        print(f"Local directory {LOCAL_DIR} does not exist.")
        return

    uploaded_count = 0
    for file_path in LOCAL_DIR.glob("*"):
        if file_path.is_file():
            key = file_path.name
            print(f"Uploading {key}...")
            try:
                s3.upload_file(str(file_path), RAW_BUCKET, key)
                uploaded_count += 1
            except Exception as e:
                print(f"Failed to upload {key}: {e}")

    print(f"Sync complete. Uploaded {uploaded_count} files.")

if __name__ == "__main__":
    sync_to_s3()
