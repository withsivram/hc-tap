from services.etl.preprocess import normalize_text
from services.etl.rule_extract import (MEDICATION_TERMS, PROBLEM_TERMS,
                                       find_spans)
from services.etl.spacy_extract import extract_entities


def test_normalize_text():
    raw = "  Hello   World  "
    assert normalize_text(raw) == "Hello World"
    assert normalize_text(None) == ""


def test_rule_extract_problem():
    text = "Patient complains of chest tightness."
    spans = list(find_spans(text, PROBLEM_TERMS, with_dose=False))
    # "chest tightness" is in PROBLEM_TERMS
    assert len(spans) >= 1
    found = [s[3] for s in spans]  # norm text
    assert "chest tightness" in found


def test_rule_extract_medication():
    text = "Started on metformin 500 mg daily."
    spans = list(find_spans(text, MEDICATION_TERMS, with_dose=True))
    # "metformin" is in MEDICATION_TERMS
    assert len(spans) >= 1
    found = [s[3] for s in spans]
    assert "metformin" in found


def test_spacy_extract_basic():
    # Basic smoke test for Spacy extractor
    text = "Patient has diabetes and takes metformin 500mg."
    ents = extract_entities(text, "test_note", "TEST")

    # Just ensure it runs without error and returns list
    assert isinstance(ents, list)
