#!/usr/bin/env python3
"""
LLM-as-a-Judge Evaluator.

Selects a random sample of processed notes and asks an LLM to evaluate
the quality of extracted entities (Precision/Recall).
"""

import json
import os
import random
import time
from typing import List

from dotenv import load_dotenv

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv()

# Configuration
SAMPLE_SIZE = 5
EXTRACTOR_RUN = os.getenv("EXTRACTOR", "spacy")
ENRICHED_DIR = f"fixtures/enriched/entities/run={EXTRACTOR_RUN}"
JUDGE_OUTPUT = f"fixtures/eval_judge_{EXTRACTOR_RUN}.json"


def get_llm_client():
    # Prefer Anthropic for judging as it's often better at reasoning/instruction following
    # But fallback to OpenAI if needed.
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic", anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    elif os.getenv("OPENAI_API_KEY"):
        return "openai", OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    else:
        raise RuntimeError(
            "No API key found for LLM Judge (need ANTHROPIC_API_KEY or OPENAI_API_KEY)"
        )


def load_enriched_data(limit=None) -> List[dict]:
    """Load all enriched entities and group by note_id."""
    path = os.path.join(ENRICHED_DIR, "part-000.jsonl")
    if not os.path.exists(path):
        print(f"[judge] No enriched data found at {path}")
        return []

    entities = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entities.append(json.loads(line))
            except Exception:
                pass

    # Group by note
    by_note = {}
    for e in entities:
        nid = e["note_id"]
        if nid not in by_note:
            by_note[nid] = []
        by_note[nid].append(e)

    return by_note


def get_original_text(note_id: str) -> str:
    path = os.path.join("fixtures/notes", f"{note_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("text", "")
    return ""


def call_judge(client_type, client, text: str, entities: List[dict]) -> dict:
    """Ask the LLM to judge the extraction."""

    entity_summary = json.dumps(
        [{"type": e["entity_type"], "text": e["text"]} for e in entities], indent=2
    )

    prompt = f"""
    You are an expert medical NLP evaluator.
    
    Review the following clinical text and the list of extracted entities (PROBLEMS and MEDICATIONS).
    
    CLINICAL TEXT:
    {text}
    
    EXTRACTED ENTITIES:
    {entity_summary}
    
    Evaluate the extraction quality on two dimensions:
    1. Precision (1-10): Are the extracted entities actually mentioned in the text and correctly classified?
    2. Recall (1-10): Did the extractor miss any obvious PROBLEMS or MEDICATIONS mentioned in the text?
    
    Provide your output as valid JSON:
    {{
        "precision_score": <int 1-10>,
        "recall_score": <int 1-10>,
        "reasoning": "<short explanation of errors or missed items>"
    }}
    """

    content = ""
    try:
        if client_type == "anthropic":
            msg = client.messages.create(
                model="claude-3-haiku-20240307",  # Use Haiku for speed/cost or Sonnet for quality
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            content = msg.content[0].text
        elif client_type == "openai":
            resp = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content

        # Parse JSON (handle markdown wrap)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[0]

        return json.loads(content)

    except Exception as e:
        print(f"[judge] Error calling LLM: {e}")
        return {"precision_score": 0, "recall_score": 0, "reasoning": f"Error: {e}"}


def main():
    print(
        f"[judge] Starting evaluation for run={EXTRACTOR_RUN} (Sample={SAMPLE_SIZE})..."
    )

    by_note = load_enriched_data()
    if not by_note:
        return

    # Random sample
    all_note_ids = list(by_note.keys())
    if len(all_note_ids) > SAMPLE_SIZE:
        sample_ids = random.sample(all_note_ids, SAMPLE_SIZE)
    else:
        sample_ids = all_note_ids

    client_type, client = get_llm_client()

    results = []
    print(f"[judge] Evaluating {len(sample_ids)} notes...")

    for nid in sample_ids:
        text = get_original_text(nid)
        if not text:
            continue

        ents = by_note[nid]
        evaluation = call_judge(client_type, client, text, ents)

        evaluation["note_id"] = nid
        evaluation["entity_count"] = len(ents)
        results.append(evaluation)
        print(
            f"  - Note {nid}: P={evaluation.get('precision_score')} R={evaluation.get('recall_score')}"
        )
        time.sleep(0.5)  # Rate limit niceness

    # Aggregate
    if results:
        avg_p = sum(r.get("precision_score", 0) for r in results) / len(results)
        avg_r = sum(r.get("recall_score", 0) for r in results) / len(results)

        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "extractor": EXTRACTOR_RUN,
            "sample_size": len(results),
            "avg_precision": round(avg_p, 2),
            "avg_recall": round(avg_r, 2),
            "details": results,
        }

        with open(JUDGE_OUTPUT, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print(f"\n[judge] Report saved to {JUDGE_OUTPUT}")
        print(f"Average Precision: {avg_p:.1f}/10")
        print(f"Average Recall:    {avg_r:.1f}/10")


if __name__ == "__main__":
    main()
