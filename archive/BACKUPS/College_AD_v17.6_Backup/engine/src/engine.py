# src/engine.py
from __future__ import annotations
from typing import Dict, Any, Tuple, List, Iterable, Union
from types import SimpleNamespace

Num = Union[int, float]
CoachObj = Union[Dict[str, Any], SimpleNamespace]

# -----------------------
# Helpers (dict or SimpleNamespace)
# -----------------------
def _get(obj: CoachObj, key: str, default=None):
    if isinstance(obj, SimpleNamespace):
        return getattr(obj, key, default)
    return obj.get(key, default)

def _set(obj: CoachObj, key: str, value) -> None:
    if isinstance(obj, SimpleNamespace):
        setattr(obj, key, value)
    else:
        obj[key] = value

def _get_traits(coach: CoachObj) -> Dict[str, Num]:
    traits = _get(coach, "traits", None)
    if traits is None:
        traits = {}
        _set(coach, "traits", traits)
    return traits

# -----------------------
# Core trait tick
# -----------------------
# Default ordered trait list (safe if config is missing)
DEFAULT_TRAITS: Tuple[str, ...] = (
    "Charisma",
    "Integrity",
    "Discipline",
    "Ego",
    "Motivation",
    "Adaptability",
    "TacticalIntelligence",
    "Leadership",
)

def _iter_traits(cfg: Dict[str, Any]) -> Iterable[str]:
    order = (cfg or {}).get("TRAITS_ORDER")
    if isinstance(order, list) and order:
        return order
    return DEFAULT_TRAITS

def _anchor_for(G: Dict[str, Any], trait: str) -> float:
    # G can be {trait: anchor} OR nested {trait: {"anchor": x}}
    v = (G or {}).get(trait, 0.0)
    if isinstance(v, dict):
        return float(v.get("anchor", 0.0))
    return float(v)

def _clamp(x: float, lo: float=-100.0, hi: float=100.0) -> float:
    return hi if x > hi else lo if x < lo else x

def advance_week_trait_engine(
    coach: CoachObj,
    cfg: Dict[str, Any],
    G: Dict[str, Any],
    ANCH: Dict[str, Any],
    CTX: Dict[str, Any],
    week: int,
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float], List[str]]:
    """
    Simple weekly gravity/decay toward anchors.
    Returns: (pre, post, delta, active_traits)
    - pre/post/delta: {trait: value}
    - active_traits: traits that changed meaningfully (> 0.001)
    Notes:
      * Uses cfg["TRAIT"]["decay"] if present; default 0.05
      * Uses cfg["TRAIT"]["max_step"] if present to cap weekly movement
      * Anchors taken from G; ANCH/CTX reserved for future modifiers
    """
    traits = _get_traits(coach)

    decay = float(((cfg or {}).get("TRAIT") or {}).get("decay", 0.05))         # pull strength
    max_step = float(((cfg or {}).get("TRAIT") or {}).get("max_step", 5.0))    # cap per week

    pre: Dict[str, float] = {}
    post: Dict[str, float] = {}
    delta: Dict[str, float] = {}
    active: List[str] = []

    for t in _iter_traits(cfg):
        cur = float(traits.get(t, 0.0))
        anch = _anchor_for(G, t)
        # basic gravity toward anchor
        step = (anch - cur) * decay
        # cap movement
        if step > max_step: step = max_step
        if step < -max_step: step = -max_step

        new = _clamp(cur + step)
        pre[t] = cur
        post[t] = new
        d = new - cur
        delta[t] = d
        if abs(d) > 1e-3:
            active.append(t)

        traits[t] = new  # write back

    # Optional: simple composite leadership = avg(Charisma, Integrity, Discipline)
    if "Leadership" in post:
        a = post.get("Charisma", pre.get("Charisma", 0.0))
        b = post.get("Integrity", pre.get("Integrity", 0.0))
        c = post.get("Discipline", pre.get("Discipline", 0.0))
        lead_new = _clamp((a + b + c) / 3.0)
        d = lead_new - post["Leadership"]
        post["Leadership"] = lead_new
        delta["Leadership"] = d
        traits["Leadership"] = lead_new
        if abs(d) > 1e-3 and "Leadership" not in active:
            active.append("Leadership")

    return pre, post, delta, active
