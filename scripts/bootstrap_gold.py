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
        # Copy the directory structure
        shutil.copytree(enriched_dir, gold_dir)
        print(f"Created gold data in {gold_dir} from enriched data")
        return True
        
    # Fallback to raw entity files
    if fallback_dir.exists():
        # Read all entity files
        entities = []
        for p in sorted(fallback_dir.glob("*.jsonl")):
            entities.extend(read_jsonl(p))
            
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
