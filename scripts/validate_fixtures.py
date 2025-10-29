import json, sys, glob, os

REQUIRED = [
  "contracts/CONTRACTS_V1.txt",
  "contracts/README.txt",
  "docs/LOCAL_DEMO.txt",
  "fixtures/notes/note_001.json",
  "fixtures/notes/note_002.json",
  "fixtures/entities/note_001.jsonl",
  "fixtures/entities/note_002.jsonl",
]

missing = [p for p in REQUIRED if not os.path.exists(p)]
if missing:
    print("Missing files:", *["- " + m for m in missing], sep="\n")
    sys.exit(1)

note_keys = {"note_id","specialty","text","checksum"}
notes = {}
for path in glob.glob("fixtures/notes/*.json"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not note_keys.issubset(data.keys()):
        print(f"[notes] Missing keys in {path}. Expected: {sorted(note_keys)}")
        sys.exit(1)
    notes[data["note_id"]] = data["text"]

entity_keys = {"note_id","run_id","entity_type","text","norm_text","begin","end","score","section"}
allowed_types = {"PROBLEM","MEDICATION"}
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
            if not entity_keys.issubset(obj.keys()):
                print(f"[entities] Missing keys in {path}:{lineno}")
                sys.exit(1)
            if obj["entity_type"] not in allowed_types:
                print(f"[entities] Invalid entity_type in {path}:{lineno}")
                sys.exit(1)
            if not isinstance(obj["begin"], int) or not isinstance(obj["end"], int) or obj["end"] <= obj["begin"]:
                print(f"[entities] begin/end invalid in {path}:{lineno}")
                sys.exit(1)
            nt = notes.get(obj["note_id"])
            if nt is not None and not (0 <= obj["begin"] < obj["end"] <= len(nt)):
                print(f"[entities] span out of bounds in {path}:{lineno}")
                sys.exit(1)
            entity_count += 1

print(f"OK ✅  notes={len(notes)}  entities={entity_count}")
