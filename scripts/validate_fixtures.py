import json, sys, glob, os
import jsonschema

print("[validator] START")

REQUIRED = [
  "contracts/CONTRACTS_V1.txt",
  "contracts/README.txt",
  "contracts/entity.schema.json",
  "contracts/note.schema.json",
  "docs/LOCAL_DEMO.txt",
  "fixtures/notes/note_001.json",
  "fixtures/notes/note_002.json",
  "fixtures/entities/note_001.jsonl",
  "fixtures/entities/note_002.jsonl",
]

missing = [p for p in REQUIRED if not os.path.exists(p)]
if missing:
    print("[validator] Missing files:"); [print(" -", m) for m in missing]; sys.exit(1)

# Load schemas
with open("contracts/entity.schema.json", "r", encoding="utf-8") as sf:
    ENTITY_SCHEMA = json.load(sf)
with open("contracts/note.schema.json", "r", encoding="utf-8") as nf:
    NOTE_SCHEMA = json.load(nf)
entity_validator = jsonschema.Draft202012Validator(ENTITY_SCHEMA)
note_validator = jsonschema.Draft202012Validator(NOTE_SCHEMA)

# Validate notes
notes = {}
for path in glob.glob("fixtures/notes/*.json"):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    err = next(note_validator.iter_errors(obj), None)
    if err:
        loc = "/".join([str(p) for p in err.path]) or "(root)"
        print(f"[notes] Schema error in {path} at {loc}: {err.message}")
        sys.exit(1)
    notes[obj["note_id"]] = obj["text"]

# Validate entities
entity_count = 0
for path in glob.glob("fixtures/entities/*.jsonl"):
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[entities] Bad JSON in {path}:{lineno}: {e}")
                sys.exit(1)

            err = next(entity_validator.iter_errors(obj), None)
            if err:
                loc = "/".join([str(p) for p in err.path]) or "(root)"
                print(f"[entities] Schema error in {path}:{lineno} at {loc}: {err.message}")
                sys.exit(1)

            nt = notes.get(obj["note_id"])
            if nt is not None:
                b, e = obj["begin"], obj["end"]
                if not (isinstance(b, int) and isinstance(e, int) and 0 <= b < e <= len(nt)):
                    print(f"[entities] span out of bounds in {path}:{lineno} (begin={b}, end={e}, len={len(nt)})")
                    sys.exit(1)
            entity_count += 1

print(f"[validator] OK ✅  notes={len(notes)}  entities={entity_count}")
