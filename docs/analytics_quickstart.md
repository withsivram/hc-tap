# Analytics & Viz (Local)

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
make dash   # opens Streamlit
```

## What to screenshot for PR

- Streamlit home with KPI tiles (notes, entities, p50, p95, error rate)
- Top Problems & Top Medications tables
- pytest -q output

## How this flips to S3/Athena later

- Keep the same columns. The only change is the data adapter: point Streamlit to S3 (s3fs) or Athena (pyathena) and set the final LOCATION in contracts/athena_entities.ddl.

