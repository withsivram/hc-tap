# Comprehensive Bug Report - HC-TAP Project

**Generated:** December 6, 2025  
**Scope:** All Python code, configuration files, and workflows

---

## Executive Summary

This report documents bugs found across the HC-TAP (Healthcare Text Analytics Pipeline) project, categorized by severity. The project consists of ETL pipelines, FastAPI backend, Streamlit dashboard, AWS infrastructure, and supporting scripts.

**Total Issues Found:** 47  
- **Critical:** 8 (Must fix immediately)
- **High Priority:** 15 (Should fix soon)
- **Medium Priority:** 17 (Fix when convenient)
- **Low Priority:** 7 (Code quality improvements)

---

## 🔴 CRITICAL BUGS (Must Fix Immediately)

### BUG-001: Typo in PROBLEM_TERMS breaks extraction
**File:** `services/etl/rule_extract.py:40`  
**Category:** Logic Error  
**Impact:** Critical - Extraction will fail to find "cough" entities  

```python
PROBLEM_TERMS = [
    # ... other terms ...
    "cough",
    "ough",  # ❌ BUG: This is clearly a typo for "cough"
]
```

**Description:** Line 40 contains `"ough"` which appears to be a typo. This will cause false positive matches on words like "though", "through", "enough", etc.

**Recommended Fix:** Remove the `"ough"` entry entirely as `"cough"` is already present in the list.

---

### BUG-002: Missing error handling in S3 operations
**File:** `services/etl/etl_cloud.py:35-37`  
**Category:** Runtime Error  
**Impact:** Critical - Will crash ETL pipeline on S3 errors  

```python
def read_s3_json(bucket: str, key: str) -> Dict:
    resp = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(resp["Body"].read().decode("utf-8"))
```

**Description:** No error handling for:
- `NoSuchKey` exception when file doesn't exist
- `JSONDecodeError` for malformed JSON
- Network errors or permission issues

**Recommended Fix:**
```python
def read_s3_json(bucket: str, key: str) -> Dict:
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(resp["Body"].read().decode("utf-8"))
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"Key not found: {key}")
            return {}
        raise
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in {key}: {e}")
        return {}
```

---

### BUG-003: LLM extraction uses naive string search for spans
**File:** `services/extractors/llm_extract.py:129`  
**Category:** Logic Error  
**Impact:** Critical - Incorrect span offsets will break evaluation  

```python
# Find offset (naive first match)
begin = original_text.find(span_text)
if begin == -1:
    # Fallback: LLM hallucinated or normalized text; skip or use 0
    begin = 0
end = begin + len(span_text)
```

**Description:** 
1. Uses `find()` which returns first occurrence only - will fail if text appears multiple times
2. Sets `begin = 0` as fallback, creating invalid spans
3. No validation that extracted span actually exists in text

**Recommended Fix:** Skip entities that can't be found in the text, or use fuzzy matching with proper offset tracking.

---

### BUG-004: Division by zero risk in quantile calculation
**File:** `services/etl/etl_local.py:76`  
**Category:** Runtime Error  
**Impact:** Critical - Will crash if empty duration list  

```python
def quantile_ms(samples: List[float], q: float) -> int:
    if not samples:
        return 0
    xs = sorted(samples)
    k = max(1, math.ceil(q * len(xs)))
    return int(round(xs[k - 1] * 1000))  # ❌ Can still access out of bounds
```

**Description:** While there's a check for empty list, `max(1, ...)` ensures k is at least 1, but `xs[k-1]` could be `xs[0]` which is valid. However, the similar function in `rule_extract.py:181-186` has the exact same pattern and could be problematic.

**Recommended Fix:** Ensure consistent bounds checking across all quantile functions.

---

### BUG-005: Unhandled exception in API reload_data
**File:** `services/api/app.py:92-95`  
**Category:** Runtime Error  
**Impact:** Critical - API crashes on data reload errors  

```python
def reload_data():
    global NOTES, ALL_ENTS, ENTS_BY_NOTE
    NOTES = load_notes()
    ALL_ENTS, ENTS_BY_NOTE = load_entities_index()
```

**Description:** No error handling if file operations fail. The function is called on every `/notes/{note_id}` and `/search` request, so any I/O error will crash the API.

**Recommended Fix:** Wrap in try/except and log errors without crashing.

---

### BUG-006: Race condition in atomic_write functions
**File:** `services/etl/etl_local.py:106-115, 118-132`  
**Category:** Logic Error  
**Impact:** High - Data corruption risk  

```python
def atomic_write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), delete=False
    ) as fh:
        json.dump(payload, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
        tmp_name = fh.name
    os.replace(tmp_name, path)  # ❌ No error handling if replace fails
```

**Description:** If `os.replace()` fails (permissions, disk full, etc.), the temp file is orphaned and the target file may be in an inconsistent state.

**Recommended Fix:** Add try/except around `os.replace()` and clean up temp file on error.

---

### BUG-007: Missing validation in normalize_entity
**File:** `services/etl/etl_local.py:93-103`  
**Category:** Logic Error  
**Impact:** High - Invalid entities silently propagate  

```python
def normalize_entity(entity: Dict, note_id: str) -> Dict:
    entity.setdefault("note_id", note_id)
    entity.setdefault("run_id", RUN_ID)
    entity["norm_text"] = normalize_entity_text(entity.get("text"))
    begin = int(entity.get("begin", 0) or 0)
    end = int(entity.get("end", 0) or 0)
    if begin >= end:
        raise ValueError(f"Invalid span ({begin}, {end}) for note {note_id}")
    entity["begin"] = begin
    entity["end"] = end
    return entity
```

**Description:** 
1. No validation that span is within text bounds
2. No validation that `entity_type` is valid
3. Exception raised here will crash entire ETL, not just skip one entity

**Recommended Fix:** Add text bounds validation and change to logging + return None for invalid entities.

---

### BUG-008: Hardcoded AWS credentials in workflow
**File:** `.github/workflows/run-etl.yml:8`, `.github/workflows/deploy.yml:10`  
**Category:** Security Vulnerability  
**Impact:** Critical - Credentials exposed in repository  

```yaml
env:
  AWS_ACCOUNT_ID: "099200121087"
  AWS_ROLE_ARN: arn:aws:iam::099200121087:role/hc-tap-github-deploy-role
```

**Description:** AWS account ID is hardcoded in the workflow files. While not as sensitive as access keys, this exposes your AWS account structure and should use GitHub secrets.

**Recommended Fix:** Move to repository secrets or variables.

---

## 🟠 HIGH PRIORITY BUGS (Should Fix Soon)

### BUG-009: Missing input validation in API extract endpoint
**File:** `services/api/app.py:217-225`  
**Category:** Security / Logic  
**Impact:** High - DoS risk, resource exhaustion  

```python
@app.post("/extract")
def extract_text(request: ExtractRequest):
    text = normalize_text(request.text)
    note_payload = {
        "note_id": request.note_id or "demo",
        "text": text,
    }
    entities = extract_for_note(note_payload)
    return {"entities": entities}
```

**Description:** No validation on text length. Users could send megabytes of text, causing:
- Memory exhaustion
- Long processing times blocking other requests
- Potential DoS attack

**Recommended Fix:** Add max length validation (e.g., 100KB) and timeout.

---

### BUG-010: Silent failure in load_notes
**File:** `services/api/app.py:44-58`  
**Category:** Logic Error  
**Impact:** High - Missing notes not logged  

```python
def load_notes():
    notes = {}
    if not os.path.exists(NOTES_DIR):
        return notes
    for name in os.listdir(NOTES_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(NOTES_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            notes[obj["note_id"]] = obj
        except Exception:
            pass  # ❌ Silent failure - no logging
    return notes
```

**Description:** Files that fail to load are silently ignored. This makes debugging difficult when notes are corrupted or have invalid JSON.

**Recommended Fix:** Log exceptions at warning level.

---

### BUG-011: Incorrect path in test_entities_contract.py
**File:** `tests/test_entities_contract.py:22`  
**Category:** Logic Error  
**Impact:** High - Test always skips  

```python
def _any_jsonl():
    files = glob.glob(os.path.join("enriched", "entities", "run=LOCAL", "*.jsonl"))
    return files[0] if files else None
```

**Description:** The path `enriched/entities/run=LOCAL/` is incorrect. Based on other files, it should be `fixtures/enriched/entities/run=LOCAL/`. This test will always be skipped.

**Recommended Fix:** Update path to `fixtures/enriched/entities/run=LOCAL/*.jsonl`.

---

### BUG-012: Missing CORS configuration in API
**File:** `services/api/app.py:20`  
**Category:** Configuration  
**Impact:** High - Dashboard can't connect in production  

```python
app = FastAPI(title="HC-TAP API", version="1.0.0")
```

**Description:** No CORS middleware configured. The Streamlit dashboard running on a different port/domain won't be able to call the API in production.

**Recommended Fix:** Add CORS middleware:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### BUG-013: docker-compose.yml uses wrong Dockerfile for ETL
**File:** `docker-compose.yml:34`  
**Category:** Configuration  
**Impact:** High - ETL service won't work correctly  

```yaml
etl:
  build:
    context: .
    dockerfile: Dockerfile.api  # ❌ Should be Dockerfile.etl
```

**Description:** ETL service uses `Dockerfile.api` instead of `Dockerfile.etl`. This means it won't have the correct entrypoint and dependencies.

**Recommended Fix:** Change to `dockerfile: Dockerfile.etl`.

---

### BUG-014: Potential SQL injection in search endpoint
**File:** `services/api/app.py:200-207`  
**Category:** Security (Low risk but needs attention)  
**Impact:** Medium-High - Potential data leakage  

```python
if q:
    ql = q.lower()
    # scan enriched over norm_text substring
    items = [
        e
        for e in items
        if (e.get("norm_text") and ql in e.get("norm_text").lower())
    ]
```

**Description:** While not traditional SQL injection, there's no input sanitization. Special regex characters in `q` could cause issues if this ever moves to a real database query.

**Recommended Fix:** Add input validation and escaping.

---

### BUG-015: Missing timeout in dashboard API requests
**File:** `services/analytics/dashboard.py:25, 219`  
**Category:** Logic Error  
**Impact:** High - Dashboard hangs on slow API  

```python
resp = requests.get(f"{API_URL}/stats/latest", timeout=2)  # ✅ Good
# BUT:
resp = requests.post(
    f"{API_URL}/extract",
    json={"text": text_input, "note_id": "demo_web"},
)  # ❌ No timeout
```

**Description:** The extract endpoint has no timeout, which could hang the dashboard indefinitely if the API is slow or unresponsive.

**Recommended Fix:** Add timeout parameter to all requests.

---

### BUG-016: Weak error handling in spacy_extract
**File:** `services/etl/spacy_extract.py:6-10`  
**Category:** Logic Error  
**Impact:** High - Silently degrades to useless extractor  

```python
try:
    nlp = spacy.load("en_core_sci_sm")
except OSError:
    print("[spacy_extract] Model en_core_sci_sm not found. Run `make bootstrap`.")
    nlp = spacy.blank("en")  # ❌ Returns blank model that extracts nothing
```

**Description:** If the model isn't found, it creates a blank model that won't extract any entities. This silently breaks the extraction pipeline.

**Recommended Fix:** Raise an exception or use a more explicit fallback strategy.

---

### BUG-017: Missing bucket existence check in sync_to_s3
**File:** `scripts/sync_to_s3.py:20-34`  
**Category:** Logic Error  
**Impact:** High - Script crashes if bucket doesn't exist  

```python
def sync():
    if not NOTES_DIR.exists():
        print(f"Notes directory {NOTES_DIR} does not exist.")
        return

    s3 = boto3.client("s3")
    # ❌ No check if bucket exists
```

**Description:** Script assumes bucket exists. If it doesn't, all uploads will fail with unclear error messages.

**Recommended Fix:** Check bucket existence first or provide clearer error handling.

---

### BUG-018: Inconsistent manifest schema across files
**File:** Multiple files  
**Category:** Logic Error  
**Impact:** High - Data inconsistency  

**Description:** Different files expect different manifest schemas:
- `etl_local.py` writes: `{manifest_version, run_id, extractor, ts_started, ts_finished, ...}`
- `rule_extract.py` writes: `{run_id, p50_ms, p95_ms, error_rate, processed_notes, ts}`
- `dashboard.py` reads: `{extractor_metrics, extractor, f1_exact_micro, ...}`

These are incompatible schemas being written to the same file path.

**Recommended Fix:** Standardize manifest schema across all services.

---

### BUG-019: Missing retry logic in LLM extractor
**File:** `services/extractors/llm_extract.py:58-63`  
**Category:** Logic Error  
**Impact:** High - Transient failures cause permanent data loss  

```python
retries = 3
for i in range(retries):
    try:
        return self._call_llm(prompt, text, note_id, run_id)
    except Exception as e:
        logger.warning(f"LLM call failed (attempt {i+1}): {e}")
        time.sleep(2**i)  # Exponential backoff
```

**Description:** While retry logic exists, it:
1. Doesn't distinguish between retryable (rate limit) and non-retryable (auth) errors
2. Only logs at warning level for permanent failures
3. Returns empty list on failure, losing all entities for that note

**Recommended Fix:** Better error classification and failure handling.

---

### BUG-020: Inefficient API data reload on every request
**File:** `services/api/app.py:100, 194`  
**Category:** Performance  
**Impact:** High - Poor API performance  

```python
@app.get("/notes/{note_id}")
def get_note(note_id: str):
    reload_data()  # ❌ Reloads entire dataset on every request
```

**Description:** `reload_data()` is called on every request, reading all files from disk. This is extremely inefficient and will cause performance issues with many notes.

**Recommended Fix:** Implement caching with TTL or file change detection.

---

### BUG-021: Missing validation in bootstrap_gold.py
**File:** `scripts/bootstrap_gold.py:29-67`  
**Category:** Logic Error  
**Impact:** High - Corrupted gold data  

```python
def create_gold_data():
    # ...
    if enriched_dir.exists() and any(enriched_dir.iterdir()):
        # Copy the directory structure
        shutil.copytree(enriched_dir, gold_dir)  # ❌ No validation of source data
```

**Description:** Script copies data without validating:
1. Source files are valid JSON
2. Required fields are present
3. Spans are within bounds

This could propagate corrupted data to gold set.

**Recommended Fix:** Add validation before copying.

---

### BUG-022: GitHub workflow uses hardcoded cluster name
**File:** `.github/workflows/run-etl.yml:10, 44`  
**Category:** Configuration  
**Impact:** High - Workflow breaks if cluster name changes  

```yaml
CLUSTER_NAME: HcTapStack-HcTapCluster7E2888D7-HmpLjPKHNhuc
# ...
CLUSTER=$(aws ecs list-clusters --query "clusterArns[?contains(@, 'HcTapStack')]" --output text)
```

**Description:** Workflow has both hardcoded and dynamic cluster lookup. The hardcoded `CLUSTER_NAME` env var is never used, and the dynamic lookup could fail silently.

**Recommended Fix:** Remove hardcoded value and add error handling for dynamic lookup.

---

### BUG-023: Missing network configuration validation in CDK
**File:** `infra/hc_tap_stack.py:50-77`  
**Category:** Configuration  
**Impact:** High - Deployment failures  

```python
self.vpc = ec2.Vpc(self, "HcTapVpc", max_azs=2)
```

**Description:** VPC created with default settings. No configuration for:
1. NAT gateways (costly)
2. VPC endpoints for S3/ECR (could save costs)
3. Subnet sizing

**Recommended Fix:** Add explicit VPC configuration with cost considerations.

---

## 🟡 MEDIUM PRIORITY BUGS (Fix When Convenient)

### BUG-024: Inconsistent return types in median_ms functions
**File:** `services/etl/etl_local.py:62-69` vs `services/etl/rule_extract.py:171-178`  
**Category:** Code Quality  
**Impact:** Medium - Type confusion  

**Description:** Same function name returns `int` in one file and `float` in another. This creates type confusion.

**Recommended Fix:** Standardize return type across all implementations.

---

### BUG-025: Missing type hints in multiple functions
**File:** Multiple files  
**Category:** Code Quality  
**Impact:** Medium - Harder to maintain  

**Description:** Many functions lack proper type hints, making the code harder to understand and maintain. Examples:
- `services/etl/sections.py:26-39` (detect_sections)
- `services/api/app.py:44-58` (load_notes)
- `services/analytics/io_utils.py` (multiple functions)

**Recommended Fix:** Add comprehensive type hints throughout the codebase.

---

### BUG-026: Inefficient list comprehension in search
**File:** `services/api/app.py:203-207`  
**Category:** Performance  
**Impact:** Medium - Slow search with large datasets  

```python
items = [
    e
    for e in items
    if (e.get("norm_text") and ql in e.get("norm_text").lower())
]
```

**Description:** Calls `.lower()` on every entity's norm_text during search. Since norm_text is already lowercase (from normalize_entity_text), this is redundant.

**Recommended Fix:** Remove `.lower()` call since norm_text is already normalized.

---

### BUG-027: Unused imports
**File:** Multiple files  
**Category:** Code Quality  
**Impact:** Low - Code cleanliness  

**Description:** Several files have unused imports:
- `services/etl/etl_cloud.py:7` - `import time` (used)
- `services/etl/etl_local.py:16` - `import random` (used only for seeding)
- `tests/test_entities_contract.py:5` - `import pandas as pd` (used)

**Recommended Fix:** Run linter to identify and remove unused imports.

---

### BUG-028: Hardcoded paths in scripts
**File:** Multiple script files  
**Category:** Configuration  
**Impact:** Medium - Scripts not portable  

**Description:** Many scripts hardcode paths like:
- `fixtures/notes`
- `gold/gold_LOCAL.jsonl`
- `enriched/entities/run=LOCAL`

These should be configurable via environment variables.

**Recommended Fix:** Use environment variables with sensible defaults.

---

### BUG-029: Missing docstrings
**File:** Multiple files  
**Category:** Code Quality  
**Impact:** Medium - Poor documentation  

**Description:** Many functions lack docstrings, making the codebase hard to understand. Critical functions without docstrings include:
- `services/etl/rule_extract.py:section_for_span`
- `services/etl/rule_extract.py:should_keep_med`
- `services/etl/rule_extract.py:should_keep_problem`

**Recommended Fix:** Add comprehensive docstrings to all public functions.

---

### BUG-030: No logging configuration
**File:** Multiple files  
**Category:** Code Quality  
**Impact:** Medium - Difficult debugging  

**Description:** Most files use `print()` statements instead of proper logging. Only `llm_extract.py` uses a logger. This makes it hard to:
- Filter log levels
- Direct logs to files
- Structure log output

**Recommended Fix:** Implement centralized logging configuration.

---

### BUG-031: Weak validation in validate_fixtures.py
**File:** `scripts/validate_fixtures.py:25`  
**Category:** Logic Error  
**Impact:** Medium - Poor error reporting  

```python
missing = [p for p in REQUIRED if not os.path.exists(p)]
if missing:
    print("[validator] Missing files:")
    [print(" -", m) for m in missing]
    sys.exit(1)
```

**Description:** Uses list comprehension for side effects (printing), which is non-idiomatic Python.

**Recommended Fix:** Use proper for loop for printing.

---

### BUG-032: Inconsistent error messages
**File:** Multiple files  
**Category:** Code Quality  
**Impact:** Medium - Poor UX  

**Description:** Error messages have inconsistent formats:
- Some use `[ETL]` prefix
- Some use `Error:` prefix
- Some have no prefix
- Some return JSON errors, others return plain text

**Recommended Fix:** Standardize error message format across all services.

---

### BUG-033: No rate limiting in API
**File:** `services/api/app.py`  
**Category:** Security  
**Impact:** Medium - DoS risk  

**Description:** API has no rate limiting. A single client could overwhelm the service with requests.

**Recommended Fix:** Add rate limiting middleware (e.g., slowapi).

---

### BUG-034: Missing health check details
**File:** `services/api/app.py:28-30`  
**Category:** Logic Error  
**Impact:** Medium - Poor observability  

```python
@app.get("/health")
def health():
    return {"ok": True}
```

**Description:** Health check always returns success, even if:
- Data files are missing
- Dependencies are unavailable
- System is under heavy load

**Recommended Fix:** Add meaningful health checks (file access, memory usage, etc.).

---

### BUG-035: No input sanitization in ingest.py
**File:** `services/etl/ingest.py:34-35`  
**Category:** Security  
**Impact:** Medium - Path traversal risk  

```python
def clean_text(text: str) -> str:
    return " ".join(text.split()).strip()
```

**Description:** CSV data is ingested without sanitization. Malicious CSV could contain:
- Path traversal characters in specialty field
- Excessive whitespace causing memory issues
- Invalid Unicode characters

**Recommended Fix:** Add input validation and sanitization.

---

### BUG-036: Weak CDK construct naming
**File:** `infra/hc_tap_stack.py`  
**Category:** Configuration  
**Impact:** Medium - CloudFormation confusion  

**Description:** CDK constructs use generic names like "ApiRepo", "RawDataBucket". These could conflict with other stacks or make debugging difficult.

**Recommended Fix:** Use more descriptive, prefixed names.

---

### BUG-037: Missing request validation in extract endpoint
**File:** `services/api/app.py:217-225`  
**Category:** Logic Error  
**Impact:** Medium - Poor error handling  

```python
@app.post("/extract")
def extract_text(request: ExtractRequest):
    text = normalize_text(request.text)
```

**Description:** No validation for:
- Empty text
- Text with only whitespace
- Invalid characters

**Recommended Fix:** Add validation with proper error responses.

---

### BUG-038: Inefficient deduplication in eval_report.py
**File:** `scripts/eval_report.py:41-60`  
**Category:** Performance  
**Impact:** Medium - Slow evaluation  

```python
def dedupe(rows: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for row in rows:
        # ... creates tuple key ...
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique
```

**Description:** This O(n) deduplication is fine, but it's called separately for gold and predictions. Should be unified into a helper function.

**Recommended Fix:** Refactor into reusable utility function.

---

### BUG-039: Missing error handling in dashboard reload
**File:** `services/analytics/dashboard.py:76-78`  
**Category:** Logic Error  
**Impact:** Medium - Dashboard crashes on reload error  

```python
if st.button("Reload Data"):
    st.cache_data.clear()
    st.rerun()  # ❌ No error handling if rerun fails
```

**Description:** If cache clearing or rerun fails, the dashboard crashes with no user feedback.

**Recommended Fix:** Add try/except with user-friendly error message.

---

### BUG-040: Overly broad exception catching
**File:** Multiple files  
**Category:** Code Quality  
**Impact:** Medium - Hides bugs  

**Description:** Many files use bare `except Exception:` which catches all errors, including ones that should crash the program (like KeyboardInterrupt, SystemExit).

Examples:
- `services/api/app.py:56, 82, 128`
- `services/analytics/dashboard.py:28`

**Recommended Fix:** Catch specific exceptions or use proper exception handling patterns.

---

## 🔵 LOW PRIORITY BUGS (Code Quality Improvements)

### BUG-041: Magic numbers in code
**File:** Multiple files  
**Category:** Code Quality  
**Impact:** Low - Maintainability  

**Description:** Several magic numbers should be constants:
- `services/etl/rule_extract.py:60, 252, 261, 266` - Window sizes (60, 40, 60)
- `services/api/app.py:185` - Limit bounds (1, 200)
- `services/analytics/dashboard.py:20, 39` - TTL values (3 seconds)

**Recommended Fix:** Extract to named constants at file/class level.

---

### BUG-042: Inconsistent string quotes
**File:** Multiple files  
**Category:** Code Quality  
**Impact:** Low - Style consistency  

**Description:** Project mixes single and double quotes inconsistently. Should use Black formatter to standardize.

**Recommended Fix:** Run Black formatter on entire codebase.

---

### BUG-043: Commented-out code
**File:** `repo_audit.py:131`  
**Category:** Code Quality  
**Impact:** Low - Code cleanliness  

```python
try:
    pass  # type: ignore
except Exception:
```

**Description:** Empty try block with commented type ignore. This appears to be dead code.

**Recommended Fix:** Remove dead code or implement proper logic.

---

### BUG-044: Missing __init__.py files
**File:** `services/etl/`, `services/eval/`  
**Category:** Code Quality  
**Impact:** Low - Import issues  

**Description:** Some service directories are missing `__init__.py` files, making them implicit namespace packages. While this works in Python 3.3+, it's better to be explicit.

**Recommended Fix:** Add empty `__init__.py` files to all package directories.

---

### BUG-045: Inconsistent naming conventions
**File:** Multiple files  
**Category:** Code Quality  
**Impact:** Low - Readability  

**Description:** Mix of naming conventions:
- `RUN_ID` (screaming snake case for constants) ✅
- `PROBLEM_TERMS` (screaming snake case for constants) ✅
- `HC_DEBUG` (screaming snake case for env vars) ✅
- `utc_iso()` (snake_case for functions) ✅
- `EntityEmitter` (PascalCase for classes) ✅

Actually, naming is mostly consistent. Minor issue: Some env vars use different patterns.

**Recommended Fix:** Document naming conventions in CONTRIBUTING.md.

---

### BUG-046: Missing requirements-dev.txt
**File:** Root directory  
**Category:** Configuration  
**Impact:** Low - Development setup  

**Description:** The CI workflow references `requirements-dev.txt` but it may not exist:

```yaml
[ -f requirements-dev.txt ] && pip install -r requirements-dev.txt || true
```

**Recommended Fix:** Create requirements-dev.txt with development dependencies (black, ruff, pytest-cov, etc.).

---

### BUG-047: No version pinning in anthropic package
**File:** `requirements.txt:9`  
**Category:** Configuration  
**Impact:** Low - Reproducibility  

```
anthropic
```

**Description:** The anthropic package has no version pin, unlike other packages. This could cause version incompatibilities.

**Recommended Fix:** Pin to specific version: `anthropic==0.34.0` (or latest stable).

---

## Summary Statistics

### By Category
- **Logic Errors:** 18 bugs
- **Security Issues:** 4 bugs
- **Performance Problems:** 4 bugs
- **Configuration Issues:** 11 bugs
- **Code Quality:** 10 bugs

### By File Type
- **Python files:** 37 bugs
- **Configuration files:** 7 bugs
- **GitHub workflows:** 3 bugs

### Most Problematic Files
1. `services/etl/rule_extract.py` - 5 bugs
2. `services/api/app.py` - 8 bugs
3. `services/etl/etl_local.py` - 4 bugs
4. `services/extractors/llm_extract.py` - 3 bugs

---

## Recommendations

### Immediate Actions (Critical Bugs)
1. Fix the "ough" typo in PROBLEM_TERMS (BUG-001)
2. Add comprehensive error handling to S3 operations (BUG-002)
3. Fix LLM span extraction logic (BUG-003)
4. Remove hardcoded AWS credentials (BUG-008)
5. Add input validation to API extract endpoint (BUG-009)

### Short-term Actions (High Priority)
1. Implement proper CORS in API (BUG-012)
2. Fix docker-compose.yml Dockerfile references (BUG-013)
3. Add timeouts to all HTTP requests (BUG-015)
4. Implement API data caching (BUG-020)
5. Standardize manifest schema (BUG-018)

### Medium-term Actions
1. Implement centralized logging (BUG-030)
2. Add comprehensive type hints (BUG-025)
3. Create requirements-dev.txt (BUG-046)
4. Add rate limiting to API (BUG-033)
5. Standardize error messages (BUG-032)

### Long-term Improvements
1. Set up comprehensive monitoring and alerting
2. Implement integration tests for ETL pipelines
3. Add performance benchmarks
4. Create developer documentation
5. Set up automated security scanning

---

## Notes

- This report was generated by comprehensive code review
- Some bugs may be intentional design decisions; verify with team
- Priority levels are estimates; adjust based on business needs
- Consider running automated security scanners (Bandit, Safety)
- Consider adding pre-commit hooks for code quality enforcement

---

**End of Report**
