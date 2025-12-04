#!/usr/bin/env python3
"""
Download MTSamples.csv from a public source.
"""

import os
import ssl
import sys
import urllib.request

# Using a stable GitHub raw URL for the dataset
URL = "https://raw.githubusercontent.com/socd06/medical-nlp/master/data/mtsamples.csv"
DEST_DIR = "data"
DEST_FILE = os.path.join(DEST_DIR, "MTSamples.csv")


def main():
    os.makedirs(DEST_DIR, exist_ok=True)

    print(f"[download] Downloading {URL} to {DEST_FILE}...")

    try:
        # Create an SSL context that ignores certificate verification errors
        # This is necessary in some sandbox/corporate environments
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(URL, context=ctx) as response, open(
            DEST_FILE, "wb"
        ) as out_file:
            out_file.write(response.read())

        print(f"[download] Success! Saved to {DEST_FILE}")

    except Exception as e:
        print(f"[download] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
