from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Tuple

# Add repo root to path for imports
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

import pandas as pd
import streamlit as st

from services.analytics.io_utils import (
    load_runs_manifest,
    infer_runs_from_folders,
    load_entities_for_run,
)

st.set_page_config(page_title="HC-TAP Analytics", layout="wide")


@st.cache_data(show_spinner=False)
def _load_runs(base_path: str, manifest_path: str) -> Tuple[List[str], pd.DataFrame]:
    manifest = load_runs_manifest(manifest_path)
    inferred = infer_runs_from_folders(base_path)
    # prefer union; manifest governs metrics
    run_ids = sorted(set(list(manifest["run_id"].astype(str)) + inferred))
    return run_ids, manifest


@st.cache_data(show_spinner=False)
def _load_entities(base_path: str, run_id: str) -> pd.DataFrame:
    return load_entities_for_run(base_path, run_id)


def _kpi_tile(label: str, value: str | int | float):
    st.metric(label, value)


def _top_counts(df: pd.DataFrame, entity_label: str, limit: int = 10) -> pd.DataFrame:
    mask = df["entity_type"].astype(str).str.upper() == entity_label.upper()
    sub = df.loc[mask, ["norm_text", "text"]].copy()
    if sub.empty:
        return pd.DataFrame(columns=["entity", "count"])
    sub["entity"] = (
        sub["norm_text"].fillna(sub["text"]).astype(str).str.strip().str.lower()
    )
    out = (
        sub.groupby("entity", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(limit)
    )
    return out


def main():
    st.title("HC-TAP: Analytics & Viz (Local Fixtures)")

    base_path = os.getenv("DATA_BASE_PATH", "enriched/entities")
    manifest_path = os.getenv("RUNS_MANIFEST_PATH", "runs/runs_local.json")

    with st.sidebar:
        st.header("Controls")
        run_ids, manifest = _load_runs(base_path, manifest_path)

        if not run_ids:
            st.warning("No runs found. Add fixtures under enriched/entities/run=<ID>/")
            st.stop()

        selected_run = st.selectbox("Run", run_ids, index=0)
        search_text = st.text_input("Filter (contains)", value="")

    df = _load_entities(base_path, selected_run)

    if df.empty:
        st.info(
            f"No entities found for run={selected_run}. Add JSONL files under {base_path}/run={selected_run}/"
        )
        st.stop()

    # Apply search filter
    if search_text:
        needle = search_text.lower()
        cols = ["text", "norm_text"]
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        df = df[
            df["text"].astype(str).str.lower().str.contains(needle)
            | df["norm_text"].astype(str).str.lower().str.contains(needle)
        ]

    # KPIs
    left, mid, right, right2, right3 = st.columns(5)
    processed_notes = int(df["note_id"].nunique()) if "note_id" in df.columns else 0
    total_entities = int(len(df))

    # manifest metrics
    p50 = p95 = err = "—"
    if not manifest.empty and selected_run in set(manifest["run_id"].astype(str)):
        row = manifest[manifest["run_id"].astype(str) == selected_run].iloc[0]
        p50 = f"{row.get('p50_ms', '—')}" if pd.notna(row.get("p50_ms")) else "—"
        p95 = f"{row.get('p95_ms', '—')}" if pd.notna(row.get("p95_ms")) else "—"
        err = (
            f"{row.get('error_rate', '—')}" if pd.notna(row.get("error_rate")) else "—"
        )

    with left:
        _kpi_tile("Processed notes", processed_notes)
    with mid:
        _kpi_tile("Total entities", total_entities)
    with right:
        _kpi_tile("p50 latency (ms)", p50)
    with right2:
        _kpi_tile("p95 latency (ms)", p95)
    with right3:
        _kpi_tile("Error rate", err)

    st.divider()

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Top 10 Problems")
        top_problems = _top_counts(df, "PROBLEM", 10)
        st.dataframe(top_problems, use_container_width=True, height=350)
        st.download_button(
            "Download Top Problems (CSV)",
            top_problems.to_csv(index=False).encode("utf-8"),
            "top_problems.csv",
        )

    with c2:
        st.subheader("Top 10 Medications")
        top_meds = _top_counts(df, "MEDICATION", 10)
        st.dataframe(top_meds, use_container_width=True, height=350)
        st.download_button(
            "Download Top Medications (CSV)",
            top_meds.to_csv(index=False).encode("utf-8"),
            "top_medications.csv",
        )

    st.divider()

    st.subheader("All Entities")
    st.dataframe(df, use_container_width=True, height=420)
    st.download_button(
        "Download All Entities (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        "entities_full.csv",
    )


if __name__ == "__main__":
    main()
