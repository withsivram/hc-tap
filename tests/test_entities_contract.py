import glob
import json
import os

import pandas as pd
import pytest

REQUIRED = {
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


def _any_jsonl():
    files = glob.glob(os.path.join("enriched", "entities", "run=LOCAL", "*.jsonl"))
    return files[0] if files else None


@pytest.mark.skipif(_any_jsonl() is None, reason="No local fixtures found")
def test_entities_columns_present():
    fp = _any_jsonl()
    df = pd.read_json(fp, lines=True)
    missing = REQUIRED - set(df.columns)
    assert not missing, f"Missing columns: {missing}"


def test_runs_manifest_schema():
    path = os.path.join("runs", "runs_local.json")
    if not os.path.exists(path):
        pytest.skip("runs_local.json missing")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list)
    if data:
        keys = set(data[0].keys())
        expected = {"run_id", "p50_ms", "p95_ms", "error_rate", "processed_notes"}
        assert expected.issubset(keys)
