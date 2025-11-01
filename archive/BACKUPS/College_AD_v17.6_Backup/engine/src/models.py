from typing import Dict, Set, List

TraitVector = Dict[str, float]

class Coach:
    id: str
    traits: TraitVector
    stress: float
    morale: float
    archetype: str
    anchor_strength: float | None
    polarity_tags: Set[str]
    active_contexts: List[str]

class School(dict):
    pass
