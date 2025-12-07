"""
spaCy-based medical entity extractor using scispaCy models.
"""

import logging
import os
from typing import List

from services.etl.rule_extract import guess_section

try:
    import spacy
    from spacy.tokens import Doc
except ImportError:
    spacy = None

logger = logging.getLogger("spacy_extract")


class SpacyExtractor:
    """
    Extract medical entities using spaCy medical NER models.
    
    Uses scispaCy models which are pre-trained on medical/scientific text.
    Best models: en_core_sci_sm, en_ner_bc5cdr_md
    """
    
    def __init__(self):
        if spacy is None:
            raise RuntimeError("spaCy not installed. Run: pip install spacy")
        
        # Try to load medical models in order of preference
        model_priority = [
            "en_ner_bc5cdr_md",  # BC5CDR corpus - diseases and chemicals
            "en_core_sci_sm",     # Small scientific/medical model
            "en_core_web_sm",     # Fallback to general English
        ]
        
        self.nlp = None
        for model_name in model_priority:
            try:
                logger.info(f"Attempting to load spaCy model: {model_name}")
                self.nlp = spacy.load(model_name)
                self.model_name = model_name
                logger.info(f"Successfully loaded spaCy model: {model_name}")
                break
            except OSError:
                logger.warning(f"Model {model_name} not found, trying next...")
                continue
        
        if self.nlp is None:
            raise RuntimeError(
                "No spaCy medical models found. Install one with:\n"
                "  pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_ner_bc5cdr_md-0.5.4.tar.gz\n"
                "  OR\n"
                "  pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz\n"
                "  OR (fallback):\n"
                "  python -m spacy download en_core_web_sm"
            )
        
        # Entity type mapping
        # spaCy BC5CDR labels: DISEASE, CHEMICAL
        # spaCy sci labels: Can vary
        # We map to: PROBLEM, MEDICATION, TEST
        self.label_map = {
            # BC5CDR model
            "DISEASE": "PROBLEM",
            "CHEMICAL": "MEDICATION",
            
            # General medical entities
            "DISORDER": "PROBLEM",
            "SYMPTOM": "PROBLEM",
            "CONDITION": "PROBLEM",
            "DRUG": "MEDICATION",
            "MEDICINE": "MEDICATION",
            
            # Standard spaCy labels (less useful for medical)
            "ORG": None,  # Skip organizations
            "PERSON": None,  # Skip person names
            "GPE": None,  # Skip locations
            "DATE": None,  # Skip dates
            "TIME": None,  # Skip times
            "CARDINAL": None,  # Skip numbers
            "MONEY": None,  # Skip money
        }
    
    def extract(self, text: str, note_id: str, run_id: str) -> List[dict]:
        """
        Extract entities from clinical text using spaCy.
        
        Args:
            text: Clinical note text
            note_id: Note identifier
            run_id: ETL run identifier
            
        Returns:
            List of entity dicts matching the schema
        """
        if not text or not text.strip():
            return []
        
        try:
            # Process text with spaCy
            doc = self.nlp(text)
            
            entities = []
            for ent in doc.ents:
                # Map entity label to our types
                entity_type = self._map_entity_type(ent.label_)
                
                # Skip unmapped types
                if entity_type is None:
                    continue
                
                # Extract normalized text (lowercase, basic cleanup)
                norm_text = self._normalize_text(ent.text)
                
                entities.append({
                    "note_id": note_id,
                    "run_id": run_id,
                    "entity_type": entity_type,
                    "text": ent.text,
                    "norm_text": norm_text,
                    "begin": ent.start_char,
                    "end": ent.end_char,
                    "score": 1.0,  # spaCy doesn't provide confidence scores for NER
                    "section": guess_section(text, ent.start_char),
                    "source": f"spacy-{self.model_name}",
                })
            
            logger.debug(f"Extracted {len(entities)} entities from note {note_id}")
            return entities
            
        except Exception as e:
            logger.error(f"spaCy extraction failed for note {note_id}: {e}")
            return []
    
    def _map_entity_type(self, spacy_label: str) -> str:
        """
        Map spaCy entity labels to our entity types.
        
        Args:
            spacy_label: Original spaCy label (e.g., "DISEASE", "CHEMICAL")
            
        Returns:
            Our entity type ("PROBLEM", "MEDICATION", "TEST") or None to skip
        """
        # Check explicit mapping
        if spacy_label in self.label_map:
            return self.label_map[spacy_label]
        
        # Default heuristics for unknown labels
        spacy_label_upper = spacy_label.upper()
        
        if any(term in spacy_label_upper for term in ["DISEASE", "DISORDER", "SYMPTOM", "CONDITION"]):
            return "PROBLEM"
        
        if any(term in spacy_label_upper for term in ["DRUG", "CHEMICAL", "MEDICINE", "MEDICATION"]):
            return "MEDICATION"
        
        if any(term in spacy_label_upper for term in ["TEST", "PROCEDURE", "LAB"]):
            return "TEST"
        
        # Skip unknown types
        logger.debug(f"Skipping unmapped spaCy label: {spacy_label}")
        return None
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize entity text for matching.
        
        Args:
            text: Original entity text
            
        Returns:
            Normalized text (lowercase, cleaned)
        """
        # Basic normalization
        norm = text.lower().strip()
        
        # Remove common medical suffixes/prefixes for better matching
        # (Keep it simple - rule-based normalization has this logic)
        
        return norm


# Convenience function for backward compatibility
def extract_for_note(note_data: dict) -> List[dict]:
    """
    Extract entities from a note dict (backward compatibility).
    
    Args:
        note_data: Dict with "note_id", "text", etc.
        
    Returns:
        List of entity dicts
    """
    extractor = SpacyExtractor()
    note_id = note_data.get("note_id", "unknown")
    text = note_data.get("text", "")
    run_id = note_data.get("run_id", "spacy")
    
    return extractor.extract(text, note_id, run_id)
