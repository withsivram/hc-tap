#!/usr/bin/env python3
"""
hc-tap quick auditor
Run from the repo root:  python repo_audit.py

What it checks:
- Required files/folders exist
- Makefile targets
- .gitignore hygiene
- Python runtime pinning via .python-version (3.12.x)
- CI workflow basics (.github/workflows/ci.yml)
- requirements.txt contains key deps
- contracts & fixtures sanity; optional schema validation if jsonschema exists
- API OpenAPI snapshot exists

Outputs a simple PASS/FAIL summary with actionable suggestions.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path.cwd()


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def exists(p: str) -> bool:
    return (ROOT / p).exists()


def check_required_files():
    reqs = [
        ".github/workflows/ci.yml",
        "requirements.txt",
        "Makefile",
        "contracts/CONTRACTS_V1.txt",
        "contracts/entity.schema.json",
        "docs/LOCAL_DEMO.txt",
        "docs/RUN_MANIFEST.txt",
        "docs/WORKING_AGREEMENTS.md",
        "docs/API_ERRORS.md",
        "docs/DISCLAIMER.md",
        "fixtures/notes/note_001.json",
        "fixtures/notes/note_002.json",
        "fixtures/entities/note_001.jsonl",
        "fixtures/entities/note_002.jsonl",
    ]
    missing = [p for p in reqs if not exists(p)]
    return missing


def check_makefile_targets():
    ok = {
        "bootstrap": False,
        "extract-local": False,
        "eval": False,
        "api-stub": False,
        "dash": False,
        "clean": False,
        "help": False,
    }
    p = ROOT / "Makefile"
    txt = read_text(p)
    for t in ok:
        if re.search(rf"^\s*{re.escape(t)}\s*:\s*$", txt, flags=re.M | re.S):
            ok[t] = True
    return ok


def check_gitignore():
    wanted = [".venv/", ".env", "__pycache__/", ".DS_Store", ".streamlit/"]
    present = {w: False for w in wanted}
    txt = read_text(ROOT / ".gitignore")
    for w in wanted:
        present[w] = w in txt
    return present


def check_python_version_pin():
    p = ROOT / ".python-version"
    if not p.exists():
        return (False, "missing .python-version (expected 3.12.x)")
    val = read_text(p).strip()
    return (val.startswith("3.12."), f"value: {val or '(empty)'} (expected 3.12.x)")


def check_requirements():
    req = read_text(ROOT / "requirements.txt")
    needed = ["jsonschema", "fastapi", "uvicorn", "pandas", "streamlit"]
    found = {pkg: False for pkg in needed}
    for line in req.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for pkg in needed:
            if re.match(rf"^{pkg}([=<>!].*)?$", line):
                found[pkg] = True
    return found


def check_ci_workflow():
    path = ROOT / ".github/workflows/ci.yml"
    txt = read_text(path)
    res = {
        "has_pull_request_trigger": "pull_request" in txt,
        "uses_python_312": re.search(r"python-version:\s*'3\.12'", txt) is not None,
        "has_pip_cache": "actions/cache" in txt and "path: ~/.cache/pip" in txt,
        "installs_requirements": "pip install -r requirements.txt" in txt,
        "workflow_name": (re.search(r"^name:\s*(.+)$", txt, flags=re.M) or [None, ""])[
            1
        ].strip(),
    }
    return res


def basic_schema_validation():
    out = {
        "note_schema_present": exists("contracts/note.schema.json"),
        "entity_schema_present": exists("contracts/entity.schema.json"),
        "validated": False,
        "errors": [],
    }
    try:
        pass  # type: ignore
    except Exception:
        out["errors"].append("jsonschema not installed; skipping schema validation.")
        return out

    if not out["note_schema_present"] or not out["entity_schema_present"]:
        out["errors"].append("schema files missing; skipping validation.")
        return out

    try:
        note_schema = json.loads(read_text(ROOT / "contracts/note.schema.json"))
        ent_schema = json.loads(read_text(ROOT / "contracts/entity.schema.json"))
        from jsonschema import Draft202012Validator

        note_val = Draft202012Validator(note_schema)
        ent_val = Draft202012Validator(ent_schema)

        # read notes
        import glob

        notes = {}
        for path in glob.glob(str(ROOT / "fixtures/notes/*.json")):
            obj = json.loads(read_text(Path(path)))
            err = next(note_val.iter_errors(obj), None)
            if err:
                out["errors"].append(f"notes schema error in {path}: {err.message}")
            notes[obj.get("note_id")] = obj.get("text", "")

        # read entities and check spans
        for path in glob.glob(str(ROOT / "fixtures/entities/*.jsonl")):
            for i, line in enumerate(read_text(Path(path)).splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    out["errors"].append(f"bad json in {path}:{i}: {e}")
                    continue
                err = next(ent_val.iter_errors(obj), None)
                if err:
                    out["errors"].append(
                        f"entities schema error in {path}:{i}: {err.message}"
                    )
                note_text = notes.get(obj.get("note_id"))
                if note_text is not None:
                    b, e = obj.get("begin"), obj.get("end")
                    if not (
                        isinstance(b, int)
                        and isinstance(e, int)
                        and 0 <= b < e <= len(note_text)
                    ):
                        out["errors"].append(
                            f"span out of bounds in {path}:{i} (begin={b}, end={e}, len={len(note_text)})"
                        )
        if not out["errors"]:
            out["validated"] = True
    except Exception as e:
        out["errors"].append(f"validation raised: {e}")
    return out


def check_openapi():
    p = ROOT / "services/api/openapi.json"
    if not p.exists():
        return (False, "missing services/api/openapi.json")
    try:
        obj = json.loads(read_text(p))
        ok = obj.get("openapi", "").startswith("3.")
        return (ok, f"openapi: {obj.get('openapi')}")
    except Exception as e:
        return (False, f"failed to parse openapi.json: {e}")


def main():
    print("== hc-tap repo audit ==\n")

    # Required files
    missing = check_required_files()
    if missing:
        print("Required files MISSING:")
        for m in missing:
            print(" -", m)
    else:
        print("Required files: OK")

    # Makefile
    mk = check_makefile_targets()
    print("\nMakefile targets:")
    for k, v in mk.items():
        print(f" - {k:13s} : {'OK' if v else 'MISSING'}")

    # .gitignore
    gi = check_gitignore()
    print("\n.gitignore essentials:")
    for k, v in gi.items():
        print(f" - {k:13s} : {'OK' if v else 'MISSING'}")

    # Python pin
    pin_ok, pin_msg = check_python_version_pin()
    print(f"\n.python-version: {'OK' if pin_ok else 'CHECK'} ({pin_msg})")

    # requirements
    reqs = check_requirements()
    print("\nrequirements.txt (key deps):")
    for k, v in reqs.items():
        print(f" - {k:11s} : {'OK' if v else 'MISSING'}")

    # CI
    ci = check_ci_workflow()
    print("\nCI workflow:")
    print(f" - name: {ci['workflow_name']}")
    print(
        f" - triggers pull_request: {'OK' if ci['has_pull_request_trigger'] else 'MISSING'}"
    )
    print(f" - python 3.12: {'OK' if ci['uses_python_312'] else 'CHECK'}")
    print(f" - pip cache: {'OK' if ci['has_pip_cache'] else 'MISSING'}")
    print(
        f" - installs requirements: {'OK' if ci['installs_requirements'] else 'MISSING'}"
    )

    # OpenAPI
    open_ok, open_msg = check_openapi()
    print(f"\nOpenAPI snapshot: {'OK' if open_ok else 'CHECK'} ({open_msg})")

    # Optional schema validation
    val = basic_schema_validation()
    print("\nContracts/fixtures validation:")
    if val["validated"]:
        print(" - OK (schemas + spans)")
    else:
        if not val["errors"]:
            print(" - Skipped")
        else:
            print(" - Issues:")
            for e in val["errors"]:
                print("   *", e)

    print("\nDone.")


if __name__ == "__main__":
    main()
