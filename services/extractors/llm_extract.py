import json
import logging
import os
import time
from typing import List

from services.etl.rule_extract import guess_section

try:
    import openai
    from openai import OpenAI
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None

logger = logging.getLogger("llm_extract")


class LLMExtractor:
    def __init__(self):
        self.provider = os.getenv("EXTRACTOR_LLM", "openai").lower()

        if self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY not set in .env")
            self.client = OpenAI(api_key=api_key)
            self.model = "gpt-4-turbo-preview"  # Or gpt-3.5-turbo

        elif self.provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = "claude-3-haiku-20240307"  # Fast & cheap

        else:
            raise ValueError(f"Unknown EXTRACTOR_LLM provider: {self.provider}")

    def extract(self, text: str, note_id: str, run_id: str) -> List[dict]:
        prompt = f"""
        You are a medical entity extractor. Extract all PROBLEMS (diseases, symptoms, diagnoses) and MEDICATIONS (drugs, treatments) from the text below.
        
        Return ONLY a valid JSON list of objects with these fields:
        - text: exact span text
        - norm_text: normalized text (lowercase, no dose)
        - entity_type: "PROBLEM" or "MEDICATION"
        
        Text:
        {text}
        """

        retries = 3
        for i in range(retries):
            try:
                return self._call_llm(prompt, text, note_id, run_id)
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {i+1}): {e}")
                time.sleep(2**i)  # Exponential backoff

        logger.error(
            f"LLM extraction failed for note {note_id} after {retries} retries."
        )
        return []

    def _call_llm(
        self, prompt: str, original_text: str, note_id: str, run_id: str
    ) -> List[dict]:
        content = ""

        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that outputs JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            content = response.choices[0].message.content

        elif self.provider == "anthropic":
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            content = message.content[0].text

        # Parse JSON
        try:
            # Clean up Markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[0]

            # Find the JSON list structure
            start = content.find("[")
            end = content.rfind("]")
            if start != -1 and end != -1:
                content = content[start : end + 1]

            data = json.loads(content)
            # Handle wrapped JSON (e.g. {"entities": [...]}) vs direct list
            items = data if isinstance(data, list) else data.get("entities", [])
            if not isinstance(items, list):
                items = []
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM JSON output. Raw content: {content}")
            return []

        # Map to our schema
        results = []
        for item in items:
            span_text = item.get("text", "")
            if not span_text:
                continue

            # Find offset (naive first match)
            begin = original_text.find(span_text)
            if begin == -1:
                # Fallback: LLM hallucinated or normalized text; skip or use 0
                begin = 0
            end = begin + len(span_text)

            results.append(
                {
                    "note_id": note_id,
                    "run_id": run_id,
                    "entity_type": item.get("entity_type", "PROBLEM").upper(),
                    "text": span_text,
                    "norm_text": item.get("norm_text", span_text).lower(),
                    "begin": begin,
                    "end": end,
                    "score": 1.0,  # Synthetic score
                    "section": guess_section(original_text, begin),
                    "source": f"llm-{self.provider}",
                }
            )

        return results
