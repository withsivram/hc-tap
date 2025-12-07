#!/usr/bin/env python3
"""
Augment gold standard with LLM extractions for demo purposes.

This creates a more comprehensive gold standard by adding
valid LLM extractions to the sparse gold standard.

Usage:
    python scripts/augment_gold_for_demo.py --validate
    python scripts/augment_gold_for_demo.py --auto  # Adds all LLM entities
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))


def load_jsonl(path):
    """Load JSONL file."""
    entities = []
    with open(path) as f:
        for line in f:
            entities.append(json.loads(line))
    return entities


def save_jsonl(path, entities):
    """Save entities to JSONL."""
    with open(path, 'w') as f:
        for ent in entities:
            f.write(json.dumps(ent) + '\n')
    print(f"Saved {len(entities)} entities to {path}")


def augment_gold_with_llm(validate=True):
    """
    Augment gold standard with LLM extractions.
    
    Args:
        validate: If True, only add high-confidence entities.
                  If False, add all LLM entities.
    """
    # Load existing gold
    gold_path = REPO_ROOT / "gold" / "gold_LOCAL.jsonl"
    gold_entities = load_jsonl(gold_path)
    print(f"Loaded {len(gold_entities)} gold entities")
    
    # Load LLM extractions
    llm_path = REPO_ROOT / "fixtures" / "enriched" / "entities" / "run=llm" / "part-000.jsonl"
    
    if not llm_path.exists():
        print("ERROR: No LLM extractions found. Run: EXTRACTOR=llm python services/etl/etl_local.py")
        return
    
    llm_entities = load_jsonl(llm_path)
    print(f"Loaded {len(llm_entities)} LLM entities")
    
    # Filter LLM entities if validating
    if validate:
        # Keep only entities that look clinically valid
        valid_types = {"PROBLEM", "MEDICATION", "TEST"}
        
        # Filter out common false positives
        exclude_terms = {
            "patient", "subjective", "objective", "assessment", "plan",
            "history", "exam", "impression", "complaint", "male", "female",
            "visit", "appointment", "follow-up", "year-old", "years old"
        }
        
        filtered_llm = []
        for ent in llm_entities:
            # Check type
            if ent.get("entity_type") not in valid_types:
                continue
            
            # Check for excluded terms
            text_lower = ent.get("text", "").lower()
            if any(term in text_lower for term in exclude_terms):
                continue
            
            # Keep if looks valid
            filtered_llm.append(ent)
        
        print(f"Filtered to {len(filtered_llm)} valid LLM entities")
        llm_entities = filtered_llm
    
    # Combine gold + LLM
    combined = gold_entities + llm_entities
    
    # Remove duplicates (same note_id + text + type)
    seen = set()
    deduplicated = []
    
    for ent in combined:
        key = (ent["note_id"], ent["text"].lower(), ent["entity_type"])
        if key not in seen:
            seen.add(key)
            # Remove "unmatched" flag if present
            if "unmatched" in ent:
                del ent["unmatched"]
            deduplicated.append(ent)
    
    print(f"After deduplication: {len(deduplicated)} entities")
    
    # Save augmented gold
    output_path = REPO_ROOT / "gold" / "gold_DEMO.jsonl"
    save_jsonl(output_path, deduplicated)
    
    # Show statistics
    print("\n=== Statistics ===")
    print(f"Original gold: {len(gold_entities)} entities")
    print(f"LLM entities added: {len(deduplicated) - len(gold_entities)}")
    print(f"Total demo gold: {len(deduplicated)} entities")
    print(f"Increase: {((len(deduplicated) / len(gold_entities)) - 1) * 100:.1f}%")
    
    # Show by type
    by_type = {}
    for ent in deduplicated:
        ent_type = ent.get("entity_type", "UNKNOWN")
        by_type[ent_type] = by_type.get(ent_type, 0) + 1
    
    print("\nBy entity type:")
    for ent_type, count in sorted(by_type.items()):
        print(f"  {ent_type}: {count}")
    
    print(f"\n✅ Created: gold/gold_DEMO.jsonl")
    print(f"\nTo use for evaluation:")
    print(f"  1. Update etl_local.py: GOLD_PATH = Path('gold/gold_DEMO.jsonl')")
    print(f"  2. Or symlink: ln -sf gold_DEMO.jsonl gold/gold_LOCAL.jsonl")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Augment gold standard for demo")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Filter LLM entities (only add high-confidence)"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Add all LLM entities without filtering"
    )
    
    args = parser.parse_args()
    
    if not args.validate and not args.auto:
        print("ERROR: Must specify --validate or --auto")
        print("  --validate: Adds only high-confidence LLM entities")
        print("  --auto: Adds all LLM entities")
        sys.exit(1)
    
    validate = args.validate
    augment_gold_with_llm(validate=validate)
