from __future__ import annotations

import re
from typing import List, Tuple

SECTION_SYNONYMS = {
    "ros": "review of systems",
    "review of systems": "review of systems",
    "pmh": "past medical history",
    "past medical history": "past medical history",
    "fhx": "family history",
    "family hx": "family history",
    "family history": "family history",
    "a/p": "plan",
    "assessment": "assessment",
    "impression": "impression",
    "plan": "plan",
    "chief complaint": "chief complaint",
    "history of present illness": "history of present illness",
    "social history": "social history",
    "medications": "medications",
}
SECTION_HEADINGS = list(SECTION_SYNONYMS.keys())


def detect_sections(text: str) -> List[Tuple[str, int, int]]:
    lower = text.lower()
    matches = []
    for heading in SECTION_HEADINGS:
        pattern = re.compile(rf"{heading}\s*:?", re.IGNORECASE)
        for match in pattern.finditer(lower):
            matches.append((heading, match.start()))
    matches.sort(key=lambda x: x[1])
    sections = []
    for idx, (name, start) in enumerate(matches):
        canonical = SECTION_SYNONYMS.get(name, name)
        end = matches[idx + 1][1] if idx + 1 < len(matches) else len(text)
        sections.append((canonical, start, end))
    return sections


def in_section(
    begin: int, end: int, sections: List[Tuple[str, int, int]], names: set[str]
) -> bool:
    for name, start, stop in sections:
        if name in names and start <= begin < stop:
            return True
    return False
