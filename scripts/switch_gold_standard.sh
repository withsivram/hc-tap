#!/bin/bash
# Quick script to switch gold standards and re-evaluate

set -e

GOLD_TYPE=${1:-demo}  # demo, original, comprehensive

echo "=== Gold Standard Switcher ==="
echo ""

case $GOLD_TYPE in
  "original"|"sparse"|"conservative")
    echo "Using ORIGINAL sparse gold (56 entities)"
    ln -sf gold_LOCAL.jsonl gold/gold_CURRENT.jsonl
    ;;
  "demo"|"augmented")
    echo "Using DEMO augmented gold (320 entities)"
    if [ ! -f gold/gold_DEMO.jsonl ]; then
      echo "Creating demo gold standard..."
      python scripts/augment_gold_for_demo.py --validate
    fi
    ln -sf gold_DEMO.jsonl gold/gold_CURRENT.jsonl
    ;;
  "comprehensive"|"full")
    echo "Using COMPREHENSIVE gold (all LLM entities)"
    if [ ! -f gold/gold_COMPREHENSIVE.jsonl ]; then
      echo "Creating comprehensive gold standard..."
      python scripts/augment_gold_for_demo.py --auto
      mv gold/gold_DEMO.jsonl gold/gold_COMPREHENSIVE.jsonl
    fi
    ln -sf gold_COMPREHENSIVE.jsonl gold/gold_CURRENT.jsonl
    ;;
  *)
    echo "Unknown gold type: $GOLD_TYPE"
    echo "Usage: $0 [original|demo|comprehensive]"
    exit 1
    ;;
esac

echo ""
echo "✅ Gold standard switched!"
echo ""
echo "To see F1 scores with new gold:"
echo "  NOTE_FILTER=gold EXTRACTOR=llm python services/etl/etl_local.py"
echo "  NOTE_FILTER=gold EXTRACTOR=enhanced python services/etl/etl_local.py"
echo ""
