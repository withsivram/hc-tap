from __future__ import annotations

import json
import os
from glob import glob
from typing import List

import pandas as pd

REQUIRED_ENTITY_KEYS = {
    "note_id",
    "run_id",
    "entity_type",
    "text",
    "norm_text",
    "begin",
    "end",
    "score",
    "section",
}


def load_runs_manifest(path: str) -> pd.DataFrame:
    """Load a runs manifest JSON list: [{run_id,p50_ms,p95_ms,error_rate,processed_notes}, ...].

    Returns empty DataFrame if file not found or invalid.
    """
    try:
        if not os.path.exists(path):
            return pd.DataFrame(
                columns=["run_id", "p50_ms", "p95_ms", "error_rate", "processed_notes"]
            )
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        expected = {"run_id", "p50_ms", "p95_ms", "error_rate", "processed_notes"}
        missing = expected - set(df.columns)
        if missing:
            return pd.DataFrame(columns=list(expected))
        return df
    except Exception:
        return pd.DataFrame(
            columns=["run_id", "p50_ms", "p95_ms", "error_rate", "processed_notes"]
        )


def infer_runs_from_folders(base_path: str) -> List[str]:
    """Find run ids by scanning subfolders 'run=*' under base_path."""
    pattern = os.path.join(base_path, "run=*")
    runs = []
    for p in glob(pattern):
        name = os.path.basename(p)
        if name.startswith("run="):
            runs.append(name.split("run=", 1)[1])
    return sorted(runs)


def load_entities_for_run(base_path: str, run_id: str) -> pd.DataFrame:
    """Read all JSONL from enriched/entities/run=<run_id> into a DataFrame."""
    folder = os.path.join(base_path, f"run={run_id}")
    files = sorted(glob(os.path.join(folder, "*.jsonl")))
    if not files:
        return pd.DataFrame(columns=list(REQUIRED_ENTITY_KEYS))

    frames = []
    for fp in files:
        try:
            frames.append(pd.read_json(fp, lines=True))
        except ValueError:
            # skip malformed file but continue
            continue

    if not frames:
        return pd.DataFrame(columns=list(REQUIRED_ENTITY_KEYS))

    df = pd.concat(frames, ignore_index=True)

    # Ensure all required columns exist
    for k in REQUIRED_ENTITY_KEYS:
        if k not in df.columns:
            df[k] = None

    # Keep only known columns + allow extra columns to pass through
    return df
