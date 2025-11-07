import os, json
import pandas as pd
import streamlit as st

RUN_ID = "LOCAL"
ENRICHED_PATH = f"fixtures/enriched/entities/run={RUN_ID}/part-000.jsonl"
RUN_MANIFEST = "fixtures/runs_LOCAL.json"

st.set_page_config(page_title="HC-TAP Dashboard (Stub)", layout="wide")
st.title("Healthcare Text Analytics Pipeline — Dashboard (Local Stub)")

# Guard rails
missing = []
if not os.path.exists(ENRICHED_PATH):
    missing.append(ENRICHED_PATH)
if not os.path.exists(RUN_MANIFEST):
    missing.append(RUN_MANIFEST)

if missing:
    st.error("Missing files:\n- " + "\n- ".join(missing))
    st.info(
        "Tip: run `make etl-stub` first to generate the enriched JSONL and manifest."
    )
    st.stop()

# Load run manifest
with open(RUN_MANIFEST, "r", encoding="utf-8") as f:
    manifest = json.load(f)

# Load JSONL into DataFrame
rows = []
with open(ENRICHED_PATH, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            rows.append(json.loads(line))

df = pd.DataFrame(rows)

# Top KPIs row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Run ID", manifest.get("run_id", RUN_ID))
col2.metric(
    "Notes processed", int(manifest.get("notes_total", df["note_id"].nunique()))
)
col3.metric("Entities total", int(manifest.get("entities_total", len(df))))
col4.metric("Errors", int(manifest.get("errors", 0)))

st.divider()

# Filters
with st.sidebar:
    st.header("Filters")
    type_filter = st.radio("Entity type", ["ALL", "PROBLEM", "MEDICATION"], index=0)
    q = st.text_input("Search text (norm_text or text)", value="").strip()
    limit = st.slider("Top N", min_value=5, max_value=20, value=10, step=1)

# Apply filters
work = df.copy()
if type_filter != "ALL":
    work = work[work["entity_type"] == type_filter]
if q:
    ql = q.lower()
    work = work[
        work["norm_text"].str.lower().str.contains(ql)
        | work["text"].str.lower().str.contains(ql)
    ]

# Summary table
with st.expander("Sample entities (first 20)"):
    st.dataframe(work.head(20))


# Top Problems / Medications
def top_counts(frame: pd.DataFrame, etype: str, n: int):
    sub = frame[frame["entity_type"] == etype]
    if sub.empty:
        return pd.DataFrame({"norm_text": [], "count": []})
    counts = (
        sub.groupby("norm_text", dropna=False)
        .size()
        .sort_values(ascending=False)
        .head(n)
        .reset_index(name="count")
    )
    return counts


left, right = st.columns(2)
with left:
    st.subheader("Top Problems")
    top_p = top_counts(work, "PROBLEM", limit)
    st.bar_chart(top_p.set_index("norm_text"))

with right:
    st.subheader("Top Medications")
    top_m = top_counts(work, "MEDICATION", limit)
    st.bar_chart(top_m.set_index("norm_text"))

st.divider()

# Latency (from manifest)
lat_c1, lat_c2 = st.columns(2)
lat_c1.metric("p50 duration (ms)", int(manifest.get("duration_ms_p50", 0)))
lat_c2.metric("p95 duration (ms)", int(manifest.get("duration_ms_p95", 0)))

st.caption(f"Data: {ENRICHED_PATH} · Manifest: {RUN_MANIFEST}")
