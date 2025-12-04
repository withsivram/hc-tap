from dataclasses import dataclass
from typing import List, Protocol


@dataclass
class Entity:
    note_id: str
    entity_type: str
    text: str
    norm_text: str
    begin: int
    end: int
    score: float = 1.0
    section: str = "unknown"
    source: str = "unknown"


class Extractor(Protocol):
    def extract(self, text: str, note_id: str, run_id: str) -> List[dict]:
        """
        Extract entities from text.
        Should return list of dicts matching the Entity schema (serialized).
        """
        ...
