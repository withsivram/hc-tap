# Run locally (stubs, no AWS)

## First time
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

## Generate enriched data & manifest
make etl-stub

## API stub (optional)
make api-stub    # open http://127.0.0.1:8000/docs

## Dashboard
make dash        # open http://localhost:8501
