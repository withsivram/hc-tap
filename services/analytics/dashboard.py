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
    # If API_URL is set and looks like cloud (not localhost), try API first
    if API_URL and "localhost" not in API_URL:
        try:
            resp = requests.get(f"{API_URL}/stats/latest", timeout=2)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass

    # Fallback to local file
    p = Path(path)
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@st.cache_data(ttl=3)
def load_entities(path: str, run_id: str = None):
    """Load entities from local file or S3 based on environment."""
    rows = []

    # Try S3 if cloud mode (API_URL is not localhost and run_id looks like cloud)
    if API_URL and "localhost" not in API_URL and run_id and run_id.startswith("cloud"):
        try:
            import boto3

            s3 = boto3.client("s3")
            # Cloud entities are at: s3://hc-tap-enriched-entities/runs/{run_id}/entities.jsonl
            bucket = "hc-tap-enriched-entities"
            key = f"runs/{run_id}/entities.jsonl"

            resp = s3.get_object(Bucket=bucket, Key=key)
            body = resp["Body"].read().decode("utf-8")

            for line in body.split("\n"):
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        log("Skipping malformed JSON in S3 object")

            log(f"Loaded {len(rows)} entities from S3: {bucket}/{key}")
            return pd.DataFrame(rows)
        except Exception as e:
            log(f"Error loading from S3: {e}, falling back to local")

    # Fallback to local file
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
    # Adjusted thresholds for realistic medical NER performance
    # 60%+ is good, 70%+ is excellent for comprehensive clinical entity extraction
    if value >= 0.70:
        return ("EXCELLENT", "normal")
    elif value >= 0.60:
        return ("GOOD", "normal")
    elif value >= 0.50:
        return ("FAIR", "off")
    else:
        return ("NEEDS IMPROVEMENT", "inverse")


st.set_page_config(page_title="Healthcare Text Analytics", layout="wide")
st.title("Healthcare Text Analytics")

if not API_BASE and not os.getenv("API_URL"):
    st.warning("Cloud API URL not set, using default local URL")

if st.button("Reload Data"):
    st.cache_data.clear()
    st.rerun()

manifest = load_manifest(str(RUN_MANIFEST))
if not manifest:
    st.warning(
        f"Manifest not found at {RUN_MANIFEST} or API. KPIs will be unavailable. Run `make etl-local` then `make eval` to generate stats, or verify 'Live Demo'."
    )
    manifest = {}  # Provide empty dict to prevent AttributeError

# Determine which metrics to show
# Priority: 1) Flat F1 scores in manifest, 2) extractor_metrics, 3) Cloud manifest
if "f1_exact_micro" in manifest:
    # Flat F1 scores available - use directly
    current_extractor = manifest.get("extractor", manifest.get("run_id", "LOCAL"))
    extractors = [current_extractor]
    metrics = manifest
    is_cloud_manifest = True  # Treat as cloud for display
elif "extractor_metrics" in manifest and manifest.get("extractor_metrics"):
    # Local mode: use extractor_metrics structure
    metrics_map = manifest.get("extractor_metrics", {})
    current_extractor = manifest.get("extractor", "local")
    extractors = sorted(metrics_map.keys()) or [current_extractor]
    
    selected_extractor = st.selectbox(
        "Select Run",
        extractors,
        index=extractors.index(current_extractor) if current_extractor in extractors else 0,
    )
    metrics = metrics_map.get(selected_extractor, {})
    is_cloud_manifest = False
else:
    # Cloud manifest (run_id only, no metrics yet)
    current_extractor = manifest.get("run_id", "cloud-latest")
    extractors = [current_extractor]
    metrics = manifest
    is_cloud_manifest = True

# If no extractor selector was shown (flat F1 or cloud mode), set selected_extractor
if 'selected_extractor' not in locals():
    selected_extractor = current_extractor

enriched_path = Path(
    f"fixtures/enriched/entities/run={selected_extractor}/part-000.jsonl"
)
entities_df = load_entities(str(enriched_path), run_id=selected_extractor)

st.caption(
    f"Manifest Source: {manifest.get('run_id', 'Local/File')} | Enriched: {enriched_path}"
)

tab_kpi, tab_demo = st.tabs(["KPIs", "Live Demo"])

with tab_kpi:
    row1 = st.columns(2)
    row1[0].metric("Run ID", manifest.get("run_id", "LOCAL"))
    row1[1].metric("Total Entities", int(len(entities_df)))

    row2 = st.columns(2)
    # Show Precision and Recall instead of Unique Notes
    precision = metrics.get("precision_exact_micro")
    recall = metrics.get("recall_exact_micro")
    row2[0].metric(
        "Precision",
        as_metric(precision),
    )
    row2[1].metric(
        "Recall", 
        as_metric(recall),
    )

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
                    timeout=10,  # 10 second timeout
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
            except requests.exceptions.Timeout:
                st.error(f"Request timed out. API at {API_URL} is not responding.")
            except requests.exceptions.ConnectionError:
                st.error(f"Could not connect to API at {API_URL}. Is it running?")
            except Exception as e:
                st.error(f"Error: {e}")
