"""
Standalone spaCy extractor for Docker container.
No external dependencies except spaCy.
"""

import logging
from typing import List

try:
    import spacy
except ImportError:
    spacy = None

logger = logging.getLogger("spacy_extract_standalone")


def guess_section(text: str, offset: int) -> str:
    """Simple section detection based on nearby headers."""
    # Look backwards for section headers
    before = text[max(0, offset-500):offset].lower()
    
    if 'chief complaint' in before or 'cc:' in before:
        return 'chief_complaint'
    elif 'history of present illness' in before or 'hpi:' in before:
        return 'hpi'
    elif 'past medical history' in before or 'pmh:' in before:
        return 'pmh'
    elif 'medications' in before or 'current medications' in before:
        return 'medications'
    elif 'allergies' in before:
        return 'allergies'
    elif 'physical exam' in before or 'exam:' in before:
        return 'physical_exam'
    elif 'assessment' in before or 'impression' in before:
        return 'assessment'
    elif 'plan' in before:
        return 'plan'
    else:
        return 'unknown'


class SpacyExtractor:
    """
    Extract medical entities using spaCy medical NER models.
    Standalone version for Docker container.
    """
    
    def __init__(self):
        if spacy is None:
            raise RuntimeError("spaCy not installed")
        
        # Try to load medical model
        model_priority = [
            "en_ner_bc5cdr_md",
            "en_core_sci_sm",
            "en_core_web_sm",
        ]
        
        self.nlp = None
        for model_name in model_priority:
            try:
                logger.info(f"Loading spaCy model: {model_name}")
                self.nlp = spacy.load(model_name)
                self.model_name = model_name
                logger.info(f"Successfully loaded: {model_name}")
                break
            except OSError:
                continue
        
        if self.nlp is None:
            raise RuntimeError("No spaCy models available")
        
        # Entity type mapping
        self.label_map = {
            "DISEASE": "PROBLEM",
            "CHEMICAL": "MEDICATION",
            "DISORDER": "PROBLEM",
            "SYMPTOM": "PROBLEM",
            "CONDITION": "PROBLEM",
            "DRUG": "MEDICATION",
            "MEDICINE": "MEDICATION",
            "ENTITY": "PROBLEM",  # Default for scispacy generic entities
        }
    
    def extract(self, text: str, note_id: str, run_id: str) -> List[dict]:
        """Extract entities from text."""
        if not text or not text.strip():
            return []
        
        try:
            doc = self.nlp(text)
            
            entities = []
            for ent in doc.ents:
                entity_type = self._map_entity_type(ent.label_)
                
                if entity_type is None:
                    continue
                
                norm_text = ent.text.lower().strip()
                
                entities.append({
                    "note_id": note_id,
                    "run_id": run_id,
                    "entity_type": entity_type,
                    "text": ent.text,
                    "norm_text": norm_text,
                    "begin": ent.start_char,
                    "end": ent.end_char,
                    "score": 1.0,
                    "section": guess_section(text, ent.start_char),
                    "source": f"spacy-{self.model_name}",
                })
            
            return entities
            
        except Exception as e:
            logger.error(f"Extraction failed for note {note_id}: {e}")
            return []
    
    def _map_entity_type(self, spacy_label: str) -> str:
        """Map spaCy labels to our types."""
        if spacy_label in self.label_map:
            return self.label_map[spacy_label]
        
        spacy_label_upper = spacy_label.upper()
        
        if any(term in spacy_label_upper for term in ["DISEASE", "DISORDER", "SYMPTOM"]):
            return "PROBLEM"
        
        if any(term in spacy_label_upper for term in ["DRUG", "CHEMICAL", "MEDICINE"]):
            return "MEDICATION"
        
        if any(term in spacy_label_upper for term in ["TEST", "PROCEDURE"]):
            return "TEST"
        
        return None
