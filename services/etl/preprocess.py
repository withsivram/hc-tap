import re
import unicodedata


def normalize_text(text: str) -> str:
    """
    Normalize text with unicode NFKC, strip, and whitespace collapse.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_entity_text(text: str) -> str:
    """
    Canonicalize entity surface text once to avoid downstream drift.
    """
    return (text or "").strip().lower()
