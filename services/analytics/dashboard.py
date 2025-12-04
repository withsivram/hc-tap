import json
import os

import pandas as pd
import streamlit as st

RUN_MANIFEST = "fixtures/runs_LOCAL.json"

st.set_page_config(page_title="HC-TAP Dashboard", layout="wide")
st.title("Healthcare Text Analytics — Extractor Comparison")

if st.button("Reload Data"):
    st.rerun()

# Load Manifest
if not os.path.exists(RUN_MANIFEST):
    st.error(f"Manifest not found at {RUN_MANIFEST}. Run `make etl-spacy` first.")
    st.stop()

try:
    with open(RUN_MANIFEST, "r", encoding="utf-8") as f:
        manifest = json.load(f)
except Exception as e:
    st.error(f"Error loading manifest: {e}")
    st.stop()

# Extractor Selector
metrics_map = manifest.get("extractor_metrics", {})
available_extractors = list(metrics_map.keys())
# Fallback to "extractor" field if metrics map empty
current_extractor = manifest.get("extractor", "spacy")
if not available_extractors and current_extractor:
    available_extractors = [current_extractor]

selected_extractor = st.selectbox(
    "Select Extractor Run",
    available_extractors,
    index=(
        available_extractors.index(current_extractor)
        if current_extractor in available_extractors
        else 0
    ),
)

# Load Enriched Data for Selection
enriched_path = f"fixtures/enriched/entities/run={selected_extractor}/part-000.jsonl"
rows = []
if os.path.exists(enriched_path):
    with open(enriched_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
else:
    st.warning(f"Enriched file not found for {selected_extractor}")

df = pd.DataFrame(rows)

# Get Metrics for Selection
metrics = metrics_map.get(selected_extractor, {})
# Fallback to top-level if not in map (legacy/bootstrap support)
if not metrics and manifest.get("extractor") == selected_extractor:
    metrics = {
        "f1_exact_micro": manifest.get("f1_exact_micro"),
        "f1_relaxed_micro": manifest.get("f1_relaxed_micro"),
        "f1_exact_micro_intersection": manifest.get("f1_exact_micro_intersection"),
        "f1_relaxed_micro_intersection": manifest.get("f1_relaxed_micro_intersection"),
    }
    # reconstruct coverage stats if available at top level
    if "coverage_gold_outside_pred_notes" in manifest:
        metrics["coverage"] = {
            "gold_outside_pred_notes": manifest.get("coverage_gold_outside_pred_notes")
        }

# --- KPIs ---
st.subheader(f"Performance: {selected_extractor.upper()}")


def kpi_delta(val, threshold=0.80):
    if val is None:
        return None, "off"
    return ("Pass" if val >= threshold else "Fail"), (
        "normal" if val >= threshold else "inverse"
    )


col1, col2, col3, col4 = st.columns(4)

# Strict
f1_exact = metrics.get("f1_exact_micro")
delta, color = kpi_delta(f1_exact)
val_str = f"{f1_exact:.3f}" if f1_exact is not None else "N/A"
col1.metric("Strict Exact F1", val_str, delta=delta, delta_color=color)

f1_relaxed = metrics.get("f1_relaxed_micro")
delta, color = kpi_delta(f1_relaxed)
val_str = f"{f1_relaxed:.3f}" if f1_relaxed is not None else "N/A"
col2.metric("Strict Relaxed F1", val_str, delta=delta, delta_color=color)

# Intersection
f1_inter_exact = metrics.get("f1_exact_micro_intersection")
delta, color = kpi_delta(f1_inter_exact)
val_str = f"{f1_inter_exact:.3f}" if f1_inter_exact is not None else "N/A"
col3.metric("Inter. Exact F1", val_str, delta=delta, delta_color=color)

f1_inter_relaxed = metrics.get("f1_relaxed_micro_intersection")
delta, color = kpi_delta(f1_inter_relaxed)
val_str = f"{f1_inter_relaxed:.3f}" if f1_inter_relaxed is not None else "N/A"
col4.metric("Inter. Relaxed F1", val_str, delta=delta, delta_color=color)

# Coverage Warning
cov = metrics.get("coverage", {})
missing_count = cov.get("gold_outside_pred_notes", 0)
if (
    f1_exact is not None
    and f1_exact < 0.80
    and f1_inter_exact is not None
    and f1_inter_exact >= 0.80
):
    st.warning(
        f"Limited coverage: {missing_count} gold notes not processed in this run."
    )

st.divider()

# --- Charts ---
st.subheader("Extraction Statistics")
c1, c2 = st.columns(2)

with c1:
    if not df.empty:
        st.metric("Entities Extracted", len(df))
        st.bar_chart(df["entity_type"].value_counts())
    else:
        st.info("No entities found.")

with c2:
    st.write("Sample Data")
    if not df.empty:
        st.dataframe(
            df[["note_id", "entity_type", "text", "norm_text"]].head(10),
            use_container_width=True,
        )

st.caption(f"Run ID: {selected_extractor} | Manifest: {RUN_MANIFEST}")

# --- Judge Report ---
judge_path = f"fixtures/eval_judge_{selected_extractor}.json"
if os.path.exists(judge_path):
    st.divider()
    st.subheader("🤖 LLM Judge Evaluation (Sample)")
    try:
        with open(judge_path, "r", encoding="utf-8") as f:
            judge_data = json.load(f)

        j_col1, j_col2, j_col3 = st.columns(3)
        j_col1.metric("Avg Precision", f"{judge_data.get('avg_precision', 0)}/10")
        j_col2.metric("Avg Recall", f"{judge_data.get('avg_recall', 0)}/10")
        j_col3.caption(
            f"Sample Size: {judge_data.get('sample_size')} notes\nDate: {judge_data.get('timestamp')}"
        )

        with st.expander("Detailed Judge Feedback"):
            for item in judge_data.get("details", []):
                st.markdown(
                    f"**Note {item.get('note_id')}** (P={item.get('precision_score')}, R={item.get('recall_score')})"
                )
                st.info(item.get("reasoning", "No reasoning provided."))
                st.divider()

    except Exception as e:
        st.error(f"Failed to load judge report: {e}")
