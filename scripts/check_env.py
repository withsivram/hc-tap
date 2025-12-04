#!/usr/bin/env python3
import os

ENV_FILE = ".env"
REQUIRED_KEYS = ["MTSAMPLES_CSV"]


def load_env(path):
    if not os.path.exists(path):
        return {}
    env = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()
    return env


def main():
    if not os.path.exists(ENV_FILE):
        print(f"[check_env] {ENV_FILE} not found. Please copy .env.template to .env")
        return

    env = load_env(ENV_FILE)
    missing = []

    print(f"Checking {ENV_FILE}...")
    for key in REQUIRED_KEYS:
        if key in env:
            print(f"  ✅ {key} is set")
        else:
            print(f"  ❌ {key} is missing")
            missing.append(key)

    if missing:
        print("\nWarning: The following keys are missing in .env:")
        for m in missing:
            print(f"  - {m}")
    else:
        print("\nEnvironment config OK.")


if __name__ == "__main__":
    main()
