# HC-TAP: Healthcare Text Analytics Pipeline

A production-style pipeline that ingests de-identified clinical notes, extracts medical entities (Problems, Medications), stores/query them, and surfaces accuracy/latency KPIs.

## Quickstart (Docker)

```bash
make docker-up
```
- **API:** http://localhost:8000/docs
- **Dashboard:** http://localhost:8501

## Development

### Requirements
- Python 3.12
- Docker

### Commands
- `make validate`: Validate note schema
- `make etl-local`: Run rule-based extraction locally
- `make eval`: Evaluate F1 scores against gold labels
- `make dash`: Run local dashboard (outside Docker)
- `make compare`: Compare default vs strict vs strict-lite profiles

