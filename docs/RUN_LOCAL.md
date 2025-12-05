# Run locally (Docker or venv)

## Docker (Recommended)
```bash
make docker-up
```
This starts the API (port 8000) and Dashboard (port 8501).

## Manual (venv)

### First time
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make bootstrap
```

### Generate Data
```bash
make etl-local
```

### Run Services
```bash
# Terminal 1: API
make api-stub

# Terminal 2: Dashboard
make dash
```

