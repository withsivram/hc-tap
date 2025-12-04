# Labeling Guide

## Definitions

### PROBLEM
Any sign, symptom, disease, or disorder mentioned in the clinical text.
- **Includes:** "diabetes", "chest pain", "shortness of breath", "hypertension".
- **Excludes:** Family history (unless relevant to current context), negated problems (unless explicitly instructed to include, usually we extract then handle negation later, but for this MVP we extract all mentions). *Clarification: This pipeline extracts mentions regardless of assertion status.*

### MEDICATION
Any drug, brand name, generic name, or vitamin/supplement.
- **Includes:** "metformin", "aspirin", "vitamin D", "lisinopril".
- **Excludes:** Diet, exercise, non-medical therapies.

## Span Rules

1. **Minimal Span:** Extract the specific term.
   - Good: "diabetes"
   - Bad: "has diabetes"

2. **Dosage (Medication):** Include dosage if immediately following the medication name.
   - Good: "lisinopril 10 mg"
   - Acceptable: "lisinopril" (if no dosage or if separated)

3. **Punctuation:** Exclude surrounding punctuation.
   - Good: "hypertension"
   - Bad: "hypertension,"

## Examples

### Positive Examples
- "Patient suffers from [diabetes] and [hypertension]." (PROBLEM)
- "Started on [metformin] 500 mg." (MEDICATION)
- "Complains of [chest tightness]." (PROBLEM)
- "Prescribed [atorvastatin]." (MEDICATION)

### Negative Examples
- "Family history of cancer." (Exclude "cancer" if strict family history rule applies, but current extractor might pick it up. For Gold, label what the patient *has* or is *discussed* as a diagnosis.)
- "[Diet] and exercise." (Not MEDICATION)

