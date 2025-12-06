#!/usr/bin/env python3
"""Initialize gold data for evaluation from fixtures."""

import json
import shutil
from pathlib import Path


def read_jsonl(path):
    """Read a jsonl file and yield each line as parsed JSON."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(objects, path):
    """Write a list of objects as jsonl to a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for obj in objects:
            json.dump(obj, f, ensure_ascii=False)
            f.write("\n")


def create_gold_data():
    """Create gold data from fixture entities."""
    # Get project root from script location
    project_root = Path(__file__).parent.parent

    # Source paths
    enriched_dir = project_root / "fixtures" / "enriched" / "entities" / "run=LOCAL"
    fallback_dir = project_root / "fixtures" / "entities"

    # Gold destination path
    gold_dir = project_root / "fixtures" / "enriched" / "entities" / "run=GOLD"

    # Clean any existing gold data
    if gold_dir.exists():
        shutil.rmtree(gold_dir)

    # Try enriched data first
    if enriched_dir.exists() and any(enriched_dir.iterdir()):
        # Validate source data before copying
        try:
            for p in enriched_dir.glob("*.jsonl"):
                for line in read_jsonl(p):
                    # Basic validation
                    required_keys = {"note_id", "entity_type", "begin", "end", "text"}
                    if not all(k in line for k in required_keys):
                        raise ValueError(f"Missing required keys in {p}")
                    if line["begin"] >= line["end"]:
                        raise ValueError(f"Invalid span in {p}: begin >= end")
        except Exception as e:
            print(f"Validation failed: {e}")
            print("Source data is invalid. Not creating gold set.")
            return False

        # Copy the directory structure
        shutil.copytree(enriched_dir, gold_dir)
        print(f"Created gold data in {gold_dir} from enriched data")
        return True

    # Fallback to raw entity files
    if fallback_dir.exists():
        # Read all entity files
        entities = []
        for p in sorted(fallback_dir.glob("*.jsonl")):
            try:
                for entity in read_jsonl(p):
                    # Validate before adding
                    required_keys = {"note_id", "entity_type", "begin", "end", "text"}
                    if not all(k in entity for k in required_keys):
                        print(f"Warning: Skipping invalid entity in {p}")
                        continue
                    if entity["begin"] >= entity["end"]:
                        print(f"Warning: Skipping invalid span in {p}")
                        continue
                    entities.append(entity)
            except Exception as e:
                print(f"Warning: Failed to read {p}: {e}")
                continue

        if entities:
            # Write to gold location
            gold_file = gold_dir / "part-000.jsonl"
            write_jsonl(entities, gold_file)
            print(f"Created gold data in {gold_file} from raw entities")
            return True

    print("Error: Could not find any source data for gold initialization")
    return False


if __name__ == "__main__":
    success = create_gold_data()
    exit(0 if success else 1)
