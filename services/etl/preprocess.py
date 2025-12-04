import re
import unicodedata


def normalize_text(text: str) -> str:
    """
    Normalize text: unicode NFKC, strip, collapse whitespace.
    """
    if not text:
        return ""
    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # Strip
    return text.strip()
