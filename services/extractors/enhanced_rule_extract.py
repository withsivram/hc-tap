"""
Enhanced rule-based medical entity extractor with medical dictionaries.

This improves on the basic rule extractor by:
1. Using comprehensive medical term dictionaries
2. Better context-aware entity detection
3. Multi-word entity matching
4. Medication dosage parsing
"""

import logging
import re
from typing import List, Set, Tuple

from services.etl.rule_extract import guess_section

logger = logging.getLogger("enhanced_rule_extract")


class EnhancedRuleExtractor:
    """
    Enhanced rule-based NER with medical dictionaries.
    
    Uses curated lists of medical terms combined with pattern matching
    for better precision/recall than basic rules.
    """
    
    def __init__(self):
        # Common medical problems (diseases, symptoms, conditions)
        self.problems = self._build_problem_dict()
        
        # Common medications
        self.medications = self._build_medication_dict()
        
        # Common tests/procedures
        self.tests = self._build_test_dict()
        
        # Medication dosage patterns
        self.dosage_pattern = re.compile(
            r'\b\d+\s*(?:mg|mcg|g|ml|cc|units?|iu|%)\b',
            re.IGNORECASE
        )
        
    def _build_problem_dict(self) -> Set[str]:
        """Build dictionary of common medical problems."""
        problems = {
            # Common diseases
            'diabetes', 'hypertension', 'asthma', 'copd', 'pneumonia',
            'bronchitis', 'influenza', 'covid', 'cancer', 'leukemia',
            'lymphoma', 'melanoma', 'carcinoma', 'arthritis', 'osteoarthritis',
            'rheumatoid arthritis', 'lupus', 'multiple sclerosis', 'parkinsons',
            'alzheimers', 'dementia', 'depression', 'anxiety', 'schizophrenia',
            'bipolar', 'adhd', 'autism', 'stroke', 'tia', 'seizure', 'epilepsy',
            'migraine', 'headache', 'angina', 'arrhythmia', 'atrial fibrillation',
            'heart failure', 'chf', 'myocardial infarction', 'mi', 'ckd',
            'chronic kidney disease', 'renal failure', 'cirrhosis', 'hepatitis',
            'pancreatitis', 'colitis', 'crohns', 'ibd', 'ulcer', 'gerd',
            'reflux', 'gastritis', 'diverticulitis', 'appendicitis', 'cholecystitis',
            'thyroid disease', 'hypothyroidism', 'hyperthyroidism', 'anemia',
            'thrombocytopenia', 'leukopenia', 'neutropenia', 'coagulopathy',
            'dvt', 'pe', 'pulmonary embolism', 'deep vein thrombosis',
            
            # Symptoms
            'pain', 'chest pain', 'abdominal pain', 'back pain', 'neck pain',
            'headache', 'dizziness', 'nausea', 'vomiting', 'diarrhea', 'constipation',
            'fever', 'chills', 'cough', 'dyspnea', 'shortness of breath', 'sob',
            'fatigue', 'weakness', 'malaise', 'syncope', 'confusion', 'lethargy',
            'edema', 'swelling', 'rash', 'pruritus', 'itching', 'bleeding',
            'hematuria', 'hemoptysis', 'hematemesis', 'melena', 'jaundice',
            'tachycardia', 'bradycardia', 'hypotension', 'hypertension',
            'tachypnea', 'wheezing', 'crackles', 'rales', 'rhonchi',
            
            # Injuries
            'fracture', 'dislocation', 'sprain', 'strain', 'laceration',
            'contusion', 'abrasion', 'burn', 'trauma', 'injury', 'wound',
        }
        
        # Add variations with common qualifiers
        expanded = set(problems)
        qualifiers = ['acute', 'chronic', 'severe', 'mild', 'moderate', 'recurrent']
        for problem in list(problems):
            for qual in qualifiers:
                expanded.add(f'{qual} {problem}')
        
        return {p.lower() for p in expanded}
    
    def _build_medication_dict(self) -> Set[str]:
        """Build dictionary of common medications."""
        meds = {
            # Cardiovascular
            'aspirin', 'asa', 'plavix', 'clopidogrel', 'warfarin', 'coumadin',
            'heparin', 'lovenox', 'enoxaparin', 'lisinopril', 'enalapril',
            'ramipril', 'losartan', 'valsartan', 'amlodipine', 'norvasc',
            'metoprolol', 'lopressor', 'atenolol', 'carvedilol', 'diltiazem',
            'verapamil', 'digoxin', 'furosemide', 'lasix', 'hydrochlorothiazide',
            'hctz', 'spironolactone', 'atorvastatin', 'lipitor', 'simvastatin',
            'pravastatin', 'rosuvastatin', 'crestor',
            
            # Diabetes
            'metformin', 'glucophage', 'glyburide', 'glipizide', 'insulin',
            'lantus', 'humalog', 'novolog', 'levemir', 'jardiance', 'empagliflozin',
            
            # Respiratory
            'albuterol', 'proventil', 'ventolin', 'ipratropium', 'atrovent',
            'fluticasone', 'flovent', 'advair', 'symbicort', 'singulair',
            'montelukast', 'prednisone', 'methylprednisolone', 'solu-medrol',
            
            # Antibiotics
            'amoxicillin', 'augmentin', 'azithromycin', 'zithromax', 'cipro',
            'ciprofloxacin', 'levofloxacin', 'levaquin', 'doxycycline',
            'cephalexin', 'keflex', 'ceftriaxone', 'rocephin', 'vancomycin',
            'penicillin', 'bactrim', 'septra', 'flagyl', 'metronidazole',
            
            # Pain/Anti-inflammatory
            'acetaminophen', 'tylenol', 'ibuprofen', 'motrin', 'advil',
            'naproxen', 'aleve', 'meloxicam', 'mobic', 'diclofenac', 'voltaren',
            'tramadol', 'ultram', 'oxycodone', 'percocet', 'hydrocodone',
            'vicodin', 'morphine', 'fentanyl', 'codeine',
            
            # GI
            'omeprazole', 'prilosec', 'pantoprazole', 'protonix', 'lansoprazole',
            'prevacid', 'famotidine', 'pepcid', 'ranitidine', 'zantac',
            'ondansetron', 'zofran', 'metoclopramide', 'reglan',
            
            # Psych
            'sertraline', 'zoloft', 'escitalopram', 'lexapro', 'fluoxetine',
            'prozac', 'citalopram', 'celexa', 'duloxetine', 'cymbalta',
            'venlafaxine', 'effexor', 'bupropion', 'wellbutrin', 'trazodone',
            'quetiapine', 'seroquel', 'olanzapine', 'zyprexa', 'risperidone',
            'risperdal', 'aripiprazole', 'abilify', 'lorazepam', 'ativan',
            'alprazolam', 'xanax', 'clonazepam', 'klonopin', 'diazepam',
            'valium', 'zolpidem', 'ambien',
            
            # Other common
            'levothyroxine', 'synthroid', 'vitamin', 'calcium', 'potassium',
        }
        
        return {m.lower() for m in meds}
    
    def _build_test_dict(self) -> Set[str]:
        """Build dictionary of common medical tests."""
        tests = {
            # Lab tests
            'cbc', 'complete blood count', 'bmp', 'cmp', 'basic metabolic panel',
            'comprehensive metabolic panel', 'lft', 'liver function tests',
            'renal function', 'creatinine', 'bun', 'glucose', 'a1c', 'hba1c',
            'hemoglobin a1c', 'lipid panel', 'cholesterol', 'triglycerides',
            'ldl', 'hdl', 'tsh', 'thyroid stimulating hormone', 'pt', 'ptt',
            'inr', 'troponin', 'bnp', 'procalcitonin', 'esr', 'crp',
            'urinalysis', 'ua', 'urine culture', 'blood culture', 'cultures',
            
            # Imaging
            'x-ray', 'xray', 'chest x-ray', 'cxr', 'ct', 'cat scan', 'ct scan',
            'mri', 'magnetic resonance', 'ultrasound', 'echo', 'echocardiogram',
            'ekg', 'ecg', 'electrocardiogram', 'stress test', 'nuclear scan',
            'pet scan', 'mammogram', 'dexa scan', 'bone density',
            
            # Procedures
            'endoscopy', 'colonoscopy', 'bronchoscopy', 'cystoscopy',
            'cardiac catheterization', 'angiogram', 'biopsy', 'lumbar puncture',
            'paracentesis', 'thoracentesis',
            
            # Vital signs
            'blood pressure', 'bp', 'heart rate', 'pulse', 'respiratory rate',
            'temperature', 'temp', 'oxygen saturation', 'o2 sat', 'spo2',
            'weight', 'bmi', 'body mass index',
        }
        
        return {t.lower() for t in tests}
    
    def extract(self, text: str, note_id: str, run_id: str) -> List[dict]:
        """
        Extract entities from clinical text.
        
        Args:
            text: Clinical note text
            note_id: Note identifier
            run_id: ETL run identifier
            
        Returns:
            List of entity dicts
        """
        if not text or not text.strip():
            return []
        
        entities = []
        text_lower = text.lower()
        
        # Extract problems
        entities.extend(self._extract_by_dictionary(
            text, text_lower, self.problems, "PROBLEM", note_id, run_id
        ))
        
        # Extract medications (with dosage handling)
        entities.extend(self._extract_medications(
            text, text_lower, note_id, run_id
        ))
        
        # Extract tests
        entities.extend(self._extract_by_dictionary(
            text, text_lower, self.tests, "TEST", note_id, run_id
        ))
        
        # Deduplicate overlapping entities (keep longer spans)
        entities = self._deduplicate_entities(entities)
        
        logger.debug(f"Extracted {len(entities)} entities from note {note_id}")
        return entities
    
    def _extract_by_dictionary(
        self, 
        text: str, 
        text_lower: str, 
        dictionary: Set[str],
        entity_type: str,
        note_id: str,
        run_id: str
    ) -> List[dict]:
        """Extract entities by dictionary matching."""
        entities = []
        
        # Sort by length (longest first) to prefer longer matches
        terms_sorted = sorted(dictionary, key=len, reverse=True)
        
        for term in terms_sorted:
            # Use word boundaries for matching
            pattern = r'\b' + re.escape(term) + r'\b'
            for match in re.finditer(pattern, text_lower):
                begin = match.start()
                end = match.end()
                original_text = text[begin:end]
                
                entities.append({
                    "note_id": note_id,
                    "run_id": run_id,
                    "entity_type": entity_type,
                    "text": original_text,
                    "norm_text": term,  # Already normalized
                    "begin": begin,
                    "end": end,
                    "score": 1.0,
                    "section": guess_section(text, begin),
                    "source": "enhanced-rule",
                })
        
        return entities
    
    def _extract_medications(
        self, 
        text: str, 
        text_lower: str, 
        note_id: str, 
        run_id: str
    ) -> List[dict]:
        """Extract medications with dosage awareness."""
        entities = []
        
        # Sort medications by length
        meds_sorted = sorted(self.medications, key=len, reverse=True)
        
        for med in meds_sorted:
            pattern = r'\b' + re.escape(med) + r'\b'
            for match in re.finditer(pattern, text_lower):
                begin = match.start()
                end = match.end()
                
                # Check if followed by dosage within 20 chars
                context_end = min(end + 20, len(text))
                context = text[end:context_end]
                dosage_match = self.dosage_pattern.search(context)
                
                if dosage_match:
                    # Include dosage in entity
                    end_with_dosage = end + dosage_match.end()
                    original_text = text[begin:end_with_dosage].strip()
                else:
                    original_text = text[begin:end]
                
                entities.append({
                    "note_id": note_id,
                    "run_id": run_id,
                    "entity_type": "MEDICATION",
                    "text": original_text,
                    "norm_text": med,  # Normalized without dosage
                    "begin": begin,
                    "end": end if not dosage_match else end_with_dosage,
                    "score": 1.0,
                    "section": guess_section(text, begin),
                    "source": "enhanced-rule",
                })
        
        return entities
    
    def _deduplicate_entities(self, entities: List[dict]) -> List[dict]:
        """
        Remove overlapping entities, keeping longer spans.
        
        For overlapping entities, prefer:
        1. Longer spans
        2. Higher confidence
        """
        if not entities:
            return []
        
        # Sort by begin position, then by span length (descending)
        sorted_entities = sorted(
            entities,
            key=lambda e: (e['begin'], -(e['end'] - e['begin']))
        )
        
        result = []
        for entity in sorted_entities:
            # Check if overlaps with any already added entity
            overlaps = False
            for existing in result:
                if self._spans_overlap(
                    entity['begin'], entity['end'],
                    existing['begin'], existing['end']
                ):
                    overlaps = True
                    break
            
            if not overlaps:
                result.append(entity)
        
        return result
    
    def _spans_overlap(
        self, 
        begin1: int, end1: int,
        begin2: int, end2: int
    ) -> bool:
        """Check if two spans overlap."""
        return not (end1 <= begin2 or end2 <= begin1)


# Convenience function for backward compatibility
def extract_for_note(note_data: dict) -> List[dict]:
    """
    Extract entities from a note dict.
    
    Args:
        note_data: Dict with "note_id", "text", etc.
        
    Returns:
        List of entity dicts
    """
    extractor = EnhancedRuleExtractor()
    note_id = note_data.get("note_id", "unknown")
    text = note_data.get("text", "")
    run_id = note_data.get("run_id", "enhanced")
    
    return extractor.extract(text, note_id, run_id)
