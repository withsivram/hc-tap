import json
import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

RUN_MANIFEST = Path("fixtures/runs_LOCAL.json")
HC_DEBUG = os.getenv("HC_TAP_DEBUG", "0") == "1"
API_BASE = os.getenv("API_BASE")
API_URL = API_BASE if API_BASE else os.getenv("API_URL", "http://localhost:8000")


def log(message: str) -> None:
    if HC_DEBUG:
        print(f"[DASH] {message}")


@st.cache_data(ttl=3)
def load_manifest(path: str):
    p = Path(path)
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@st.cache_data(ttl=3)
def load_entities(path: str):
    rows = []
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(rows)
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    log(f"Skipping malformed JSON in {p}")
    return pd.DataFrame(rows)


def as_metric(value):
    return f"{value:.3f}" if value is not None else "N/A"


def badge(value):
    if value is None:
        return ("N/A", "off")
    return (
        "PASS" if value >= 0.80 else "FAIL",
        "normal" if value >= 0.80 else "inverse",
    )


st.set_page_config(page_title="HC-TAP Dashboard", layout="wide")
st.title("Healthcare Text Analytics — Phase-3 KPIs")

if not API_BASE and not os.getenv("API_URL"):
    st.warning("Cloud API URL not set, using default local URL")

if st.button("Reload Data"):
    st.cache_data.clear()
    st.rerun()

manifest = load_manifest(str(RUN_MANIFEST))
if not manifest:
    st.warning(
        f"Manifest not found at {RUN_MANIFEST}. KPIs will be unavailable. Run `make etl-local` then `make eval` to generate stats, or verify 'Live Demo'."
    )
    manifest = {}  # Provide empty dict to prevent AttributeError

metrics_map = manifest.get("extractor_metrics", {})
current_extractor = manifest.get("extractor", "local")
extractors = sorted(metrics_map.keys()) or [current_extractor]

selected_extractor = st.selectbox(
    "Select Run",
    extractors,
    index=extractors.index(current_extractor) if current_extractor in extractors else 0,
)
metrics = metrics_map.get(selected_extractor, {})
if not metrics:
    metrics = {
        "f1_exact_micro": manifest.get("f1_exact_micro"),
        "f1_relaxed_micro": manifest.get("f1_relaxed_micro"),
        "f1_exact_micro_intersection": manifest.get("f1_exact_micro_intersection"),
        "f1_relaxed_micro_intersection": manifest.get("f1_relaxed_micro_intersection"),
        "coverage": {
            "gold_outside_pred_notes": manifest.get(
                "coverage_gold_outside_pred_notes", 0
            ),
        },
    }

enriched_path = Path(
    f"fixtures/enriched/entities/run={selected_extractor}/part-000.jsonl"
)
entities_df = load_entities(str(enriched_path))

st.caption(f"Manifest: {RUN_MANIFEST} | Enriched: {enriched_path}")

tab_kpi, tab_demo = st.tabs(["KPIs", "Live Demo"])

with tab_kpi:
    row1 = st.columns(2)
    row1[0].metric("Run ID", manifest.get("run_id", "LOCAL"))
    row1[1].metric("Total Entities", int(len(entities_df)))

    row2 = st.columns(2)
    row2[0].metric(
        "Unique Notes",
        int(entities_df["note_id"].nunique()) if not entities_df.empty else 0,
    )
    row2[1].metric("Errors", int(manifest.get("errors", 0)))

    st.subheader("KPI — Strict F1")
    strict_cols = st.columns(2)
    strict_exact = metrics.get("f1_exact_micro")
    strict_label, strict_color = badge(strict_exact)
    strict_cols[0].metric(
        "Strict Exact F1",
        as_metric(strict_exact),
        delta=strict_label,
        delta_color=strict_color,
    )

    strict_relaxed = metrics.get("f1_relaxed_micro")
    rel_label, rel_color = badge(strict_relaxed)
    strict_cols[1].metric(
        "Strict Relaxed F1",
        as_metric(strict_relaxed),
        delta=rel_label,
        delta_color=rel_color,
    )

    st.subheader("KPI — Intersection F1")
    inter_cols = st.columns(2)
    inter_exact = metrics.get("f1_exact_micro_intersection")
    inter_label, inter_color = badge(inter_exact)
    inter_cols[0].metric(
        "Intersection Exact F1",
        as_metric(inter_exact),
        delta=inter_label,
        delta_color=inter_color,
    )

    inter_relaxed = metrics.get("f1_relaxed_micro_intersection")
    inter_rel_label, inter_rel_color = badge(inter_relaxed)
    inter_cols[1].metric(
        "Intersection Relaxed F1",
        as_metric(inter_relaxed),
        delta=inter_rel_label,
        delta_color=inter_rel_color,
    )

    cov = metrics.get("coverage", {}) or {}
    if (
        strict_exact is not None
        and strict_exact < 0.80
        and inter_exact is not None
        and inter_exact >= 0.80
    ):
        st.warning(
            f"Coverage gap: {cov.get('gold_outside_pred_notes', 0)} gold notes missing from predictions despite strong intersection performance."
        )

    st.divider()
    st.subheader("Extraction Breakdown")
    chart_cols = st.columns(2)

    with chart_cols[0]:
        if entities_df.empty:
            st.info("No entities found for this run.")
        else:
            st.metric("Total Entities", len(entities_df))
            st.bar_chart(entities_df["entity_type"].value_counts())

    with chart_cols[1]:
        if entities_df.empty:
            st.info("No rows to display.")
        else:
            st.dataframe(
                entities_df[["note_id", "entity_type", "text", "norm_text"]].head(15),
                use_container_width=True,
            )

with tab_demo:
    st.header("Live Extraction Demo")
    st.markdown(f"**API Endpoint:** `{API_URL}/extract`")

    text_input = st.text_area(
        "Enter clinical note text:",
        height=200,
        value="Patient presents with severe chest pain and nausea. Prescribed aspirin 81mg daily.",
    )

    if st.button("Extract Entities", type="primary"):
        with st.spinner("Extracting..."):
            try:
                resp = requests.post(
                    f"{API_URL}/extract",
                    json={"text": text_input, "note_id": "demo_web"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    ents = data.get("entities", [])
                    st.success(f"Success! Found {len(ents)} entities.")
                    if ents:
                        st.dataframe(pd.DataFrame(ents))
                    else:
                        st.info("No entities detected.")
                else:
                    st.error(f"API Error {resp.status_code}: {resp.text}")
            except requests.exceptions.ConnectionError:
                st.error(f"Could not connect to API at {API_URL}. Is it running?")
            except Exception as e:
                st.error(f"Error: {e}")
