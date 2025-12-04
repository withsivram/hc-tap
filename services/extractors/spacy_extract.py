import os
from typing import List

import spacy

from services.etl.rule_extract import guess_section


class SpacyExtractor:
    def __init__(self):
        model_name = os.getenv("SPACY_MODEL", "en_core_sci_sm")
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            print(
                f"[SpacyExtractor] Model {model_name} not found. Run `make bootstrap` or install it."
            )
            self.nlp = spacy.blank("en")

    def extract(self, text: str, note_id: str, run_id: str) -> List[dict]:
        doc = self.nlp(text)
        entities = []

        for ent in doc.ents:
            # Basic heuristic mapping (same as before)
            etype = "PROBLEM"
            if ent.label_ in ["CHEMICAL", "SIMPLE_CHEMICAL"]:
                etype = "MEDICATION"
            elif ent.label_ in ["DISEASE", "CANCER", "ORGAN_TISSUE_STRUCTURE"]:
                etype = "PROBLEM"

            norm = ent.text.lower()
            if any(x in norm for x in ["mg", "tablet", "capsule", "injection"]):
                etype = "MEDICATION"

            entities.append(
                {
                    "note_id": note_id,
                    "run_id": run_id,
                    "entity_type": etype,
                    "text": ent.text,
                    "norm_text": norm,
                    "begin": ent.start_char,
                    "end": ent.end_char,
                    "score": 0.85,
                    "section": guess_section(text, ent.start_char),
                    "source": "spacy",
                }
            )
        return entities
