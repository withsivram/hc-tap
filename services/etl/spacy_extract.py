import spacy

from services.etl.rule_extract import guess_section

# Load model globally (lazy load would be better in prod)
try:
    nlp = spacy.load("en_core_sci_sm")
except OSError:
    print("[spacy_extract] Model en_core_sci_sm not found. Run `make bootstrap`.")
    nlp = spacy.blank("en")


def extract_entities(text: str, note_id: str, run_id: str):
    """
    Extract entities using Spacy NER model.
    Returns list of dicts compatible with rule_extract.py output.
    """
    doc = nlp(text)
    entities = []

    for ent in doc.ents:
        # Map Spacy labels to our schema if needed
        # scispacy uses specific labels like ENTITY, DISEASE, CHEMICAL
        # For now, we'll map broad categories or keep as is.

        # Simple mapping strategy for this MVP:
        etype = "PROBLEM"  # Default
        if ent.label_ in ["CHEMICAL", "SIMPLE_CHEMICAL"]:
            etype = "MEDICATION"
        elif ent.label_ in [
            "DISEASE",
            "CANCER",
            "ORGAN_TISSUE_STRUCTURE",
        ]:  # Approximate mapping
            etype = "PROBLEM"
        else:
            # Skip unknown types or map to PROBLEM for coverage
            # In a real system, we'd have a strict label map
            if ent.label_ == "ENTITY":
                # Scispacy often outputs ENTITY for general things
                # Heuristic: check against med terms or keep generic
                pass

        # We'll just capture everything for now to see what we get,
        # but normalized to our 2 expected types for the Dashboard

        # Heuristic override based on text analysis (mini-rules)
        norm = ent.text.lower()
        if any(x in norm for x in ["mg", "tablet", "capsule", "injection"]):
            etype = "MEDICATION"

        obj = {
            "note_id": note_id,
            "run_id": run_id,
            "entity_type": etype,
            "text": ent.text,
            "norm_text": norm,
            "begin": ent.start_char,
            "end": ent.end_char,
            "score": 0.85,  # Model confidence (placeholder)
            "section": guess_section(text, ent.start_char),
            "source": "scispacy",
        }
        entities.append(obj)

    return entities
