import json, sys, glob, os
import jsonschema

print("[validator] START")

REQUIRED = [
  "contracts/CONTRACTS_V1.txt",
  "contracts/README.txt",
  "docs/LOCAL_DEMO.txt",
  "contracts/entity.schema.json",
  "fixtures/notes/note_001.json",
  "fixtures/notes/note_002.json",
  "fixtures/entities/note_001.jsonl",
  "fixtures/entities/note_002.jsonl",
]

missing = [p for p in REQUIRED if not os.path.exists(p)]
if missing:
    print("[validator] Missing files:"); [print(" -", m) for m in missing]; sys.exit(1)

# Load notes
note_keys = {"note_id","specialty","text","checksum"}
notes = {}
for path in glob.glob("fixtures/notes/*.json"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not note_keys.issubset(data.keys()):
        print(f"[notes] Missing keys in {path}. Expected: {sorted(note_keys)}"); sys.exit(1)
    notes[data["note_id"]] = data["text"]

# Load entity JSON Schema
with open("contracts/entity.schema.json", "r", encoding="utf-8") as sf:
    ENTITY_SCHEMA = json.load(sf)
validator = jsonschema.Draft202012Validator(ENTITY_SCHEMA)

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
                print(f"[entities] Bad JSON in {path}:{lineno}: {e}"); sys.exit(1)

            # JSON Schema validation
            errors = sorted(validator.iter_errors(obj), key=lambda e: e.path)
            if errors:
                first = errors[0]
                loc = "/".join([str(p) for p in first.path]) or "(root)"
                print(f"[entities] Schema error in {path}:{lineno} at {loc}: {first.message}")
                sys.exit(1)

            # Extra bounds check against note text
            nt = notes.get(obj["note_id"])
            if nt is not None:
                b, e = obj["begin"], obj["end"]
                if not (isinstance(b, int) and isinstance(e, int) and 0 <= b < e <= len(nt)):
                    print(f"[entities] span out of bounds in {path}:{lineno} (begin={b}, end={e}, len={len(nt)})")
                    sys.exit(1)

            entity_count += 1

print(f"[validator] OK ✅  notes={len(notes)}  entities={entity_count}")
