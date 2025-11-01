# engine/src/reg_engine.py — v17.6 (Option A: donor personality + memory hook)
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple, Union
from types import SimpleNamespace
import random

# Personality & donor memory (new)
try:
    from .personality_engine import generate as gen_persona, donor_propensity
except Exception:
    # Safe fallback if file is missing
    def gen_persona(seed: str, role: str, overrides=None): return {"id": seed, "archetype": "Donor_Patron", "traits": {}, "modifiers": {}, "style": {}}
    def donor_propensity(persona, school_sentiment: float, prestige: float) -> float: return 0.5

try:
    from .donor_memory import get_or_create_donor, record_pledge, apply_decay
except Exception:
    def get_or_create_donor(world, school_name, persona=None):
        return {"name": f"{school_name} Donor(Fallback)", "persona": persona or {}, "trust": 0.5, "leverage": 0.0, "history": []}
    def record_pledge(world, school_name, **kwargs): return {}
    def apply_decay(world, school_name, weeks=1): return None

Coach = Union[Dict[str, Any], SimpleNamespace]

# ---------------------------
# Helpers
# ---------------------------
def _get(coach: Coach, key: str, default=None):
    if isinstance(coach, SimpleNamespace):
        return getattr(coach, key, default)
    return coach.get(key, default)

def _set(coach: Coach, key: str, value) -> None:
    if isinstance(coach, SimpleNamespace):
        setattr(coach, key, value)
    else:
        coach[key] = value

def _choose_coach(coaches: List[Coach], rng: random.Random) -> Optional[Coach]:
    return rng.choice(coaches) if coaches else None

def _tier_from_weights(tier_weights: Dict[str, float], rng: random.Random) -> str:
    items = list(tier_weights.items())  # [(tier, w)]
    total = sum(max(w, 0.0) for _, w in items) or 1.0
    roll = rng.random() * total
    acc = 0.0
    for tier, w in items:
        acc += max(w, 0.0)
        if roll <= acc:
            return tier
    return items[-1][0]

def _pick_event_from_catalog(reg_catalog: List[Dict[str, Any]], tier: str, rng: random.Random) -> Optional[Dict[str, Any]]:
    pool = [e for e in reg_catalog if e.get("tier") == tier]
    if not pool:
        pool = reg_catalog[:]
    if not pool:
        return None
    return rng.choice(pool)

def _rand_intensity(rng: random.Random, intensity_field) -> float:
    if isinstance(intensity_field, (list, tuple)) and len(intensity_field) >= 2:
        lo, hi = float(intensity_field[0]), float(intensity_field[1])
        if hi < lo:
            lo, hi = hi, lo
        return rng.uniform(lo, hi)
    try:
        return float(intensity_field)
    except Exception:
        return 0.0

# ---------------------------
# Donor helpers (new)
# ---------------------------
def _is_donor_event(template: Dict[str, Any]) -> bool:
    cat = (template.get("category") or "").lower()
    if cat in ("donor", "alumni"):
        return True
    eid = (template.get("id") or template.get("event_id") or "").upper()
    # heuristic for older/simple catalogs
    return ("DONOR" in eid) or ("ALUMNI" in eid) or ("PLEDGE" in eid)

def _school_target_from(ev: Dict[str, Any]) -> Optional[str]:
    # Prefer explicit school field, otherwise a named target, else None
    school = ev.get("school") or ev.get("target_school")
    if school:
        return str(school)
    tgts = ev.get("targets") or ev.get("target") or []
    if isinstance(tgts, str):
        tgts = [tgts]
    # If a specific school name is among targets, pick it; else None
    for t in tgts:
        if isinstance(t, str) and (" " in t or t.endswith("U") or t.endswith("University")):
            return t
    return None

def _apply_effect(
    ev: Dict[str, Any],
    coaches: List[Coach],
    world: Dict[str, Any],
    rng: random.Random
) -> Tuple[str, str]:
    """
    Apply a lightweight effect so the sim 'moves' even before deep systems exist.
    Returns (target_str, effect_str) describing what changed (for CSV).
    """
    targets = ev.get("targets") or ev.get("target") or []
    if isinstance(targets, (str,)):
        targets = [targets]
    intensity = float(ev.get("intensity", 0.0))

    target_desc = ""
    effect_desc = ""

    # World-level adjustments
    picked = None
    if targets:
        picked = rng.choice(targets)

    if picked in ("Prestige", "Facilities", "Integrity", "MediaHeat"):
        world.setdefault("metrics", {})
        metrics = world["metrics"]
        old = float(metrics.get(picked, 0.0))
        new = old + intensity
        metrics[picked] = new
        target_desc = picked
        effect_desc = f"{old:+.2f}->{new:+.2f}"
        return target_desc, effect_desc

    # Coach-level adjustment (fallback)
    if coaches:
        c = _choose_coach(coaches, rng)
        if c is not None:
            mh = float(_get(c, "media_heat", 0.0))
            _set(c, "media_heat", mh + (0.5 * intensity))
            name = _get(c, "name", "coach")
            target_desc = f"coach:{name}"
            effect_desc = f"media_heat {mh:+.2f}->{mh + 0.5*intensity:+.2f}"
            return target_desc, effect_desc

    target_desc = str(picked or "global")
    effect_desc = f"intensity {intensity:+.2f}"
    return target_desc, effect_desc

# ---------------------------
# Main entry: advance_reg_tick
# ---------------------------
def advance_reg_tick(
    coaches: List[Coach],
    world: Dict[str, Any],
    cfg: Dict[str, Any],
    reg_catalog: List[Dict[str, Any]],
    rng: random.Random,
    week: int
) -> List[Dict[str, Any]]:
    """
    Chooses a handful of REG events, applies lightweight effects, and returns
    a normalized list of event dicts with guaranteed keys:
      - week (int)
      - event_id (str)
      - intensity (float)
      - target (str)
      - effect (str)
      - notes (str; optional summary)
    """
    reg_cfg = (cfg or {}).get("REG", {})
    weekly_rolls = int(reg_cfg.get("weekly_rolls", 3))
    tier_weights = reg_cfg.get("weights", {"positive": 0.45, "neutral": 0.25, "negative": 0.30})

    results: List[Dict[str, Any]] = []

    if not reg_catalog or weekly_rolls <= 0:
        return results

    # light decay for donor memory each week
    for s in (world.get("schools") or []):
        sname = s.get("name")
        if sname:
            apply_decay(world, sname, weeks=1)

    for _ in range(weekly_rolls):
        tier = _tier_from_weights(tier_weights, rng)
        template = _pick_event_from_catalog(reg_catalog, tier, rng)
        if not template:
            continue

        event_id = template.get("event_id") or template.get("id") or "UNKNOWN_EVENT"
        intensity = _rand_intensity(rng, template.get("intensity", 0.0))

        # ---- Donor personality hook (safe, optional)
        notes_extra = ""
        if _is_donor_event(template):
            # pick a school for donor context if provided, else ignore
            school_name = _school_target_from(template) or (world.get("schools", [{}])[0].get("name") if world.get("schools") else None)
            sentiment = 0.0
            prestige = float((world.get("metrics") or {}).get("Prestige", 0.0))
            persona = gen_persona(seed=f"DONOR_{school_name or 'GLOBAL'}", role="donor", overrides=None)
            # stash persona in donor memory for that school
            if school_name:
                get_or_create_donor(world, school_name, persona=persona)
            prop = donor_propensity(persona, school_sentiment=sentiment, prestige=prestige)
            # Scale intensity mildly (donor more/less “on” this week)
            intensity *= (0.75 + 0.5 * prop)  # scales ~0.75..1.225
            notes_extra = f" | Donor Persona:{persona.get('archetype')} prop={prop:.2f}"
            # Record pledge if event specifies amount / earmark (optional fields)
            donor_amt = template.get("donor_delta")
            if donor_amt and school_name:
                try:
                    amt = float(donor_amt)
                    earmark = template.get("earmark") or ""
                    record_pledge(world, school_name, week=week, amount=amt, earmark=earmark, due_week=None)
                    notes_extra += f" | pledge:${amt:,.0f}{(' earmark:'+earmark) if earmark else ''}"
                except Exception:
                    pass  # ignore malformed donor_delta

        # Construct working event dict
        ev: Dict[str, Any] = {
            "week": week,
            "event_id": event_id,
            "tier": tier,
            "intensity": intensity,
            "targets": template.get("targets") or [],
            "notes": (template.get("notes") or template.get("summary") or "") + notes_extra,
            # pass through optional fields so downstream systems can read them later
            "school": template.get("school"),
            "category": template.get("category"),
        }

        # Apply simple effect to world/coach
        target_str, effect_str = _apply_effect(ev, coaches, world, rng)

        # CSV-friendly output
        normalized = {
            "week": week,
            "event_id": event_id,
            "intensity": round(float(intensity), 2),
            "target": target_str,
            "effect": effect_str,
            "notes": ev["notes"],
        }
        results.append(normalized)

    return results
