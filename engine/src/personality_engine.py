
# engine/src/personality_engine.py — v17.6 Personality Core
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Tuple
import json, hashlib, random

ROOT = Path(__file__).resolve().parents[2]

def _load_env() -> Dict[str,str]:
    env = {}
    ef = ROOT / ".env"
    if ef.exists():
        for line in ef.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k,v = line.split("=",1)
                env[k.strip()] = v.strip()
    return env

ENV = _load_env()
CONFIG_DIR = (ROOT / ENV.get("CONFIG_DIR", "configs")).resolve()

def _load_profiles() -> Dict[str, Any]:
    p_engine = ROOT / "engine" / "config" / "personality_profiles.json"
    p_env = CONFIG_DIR / "personality_profiles.json"
    for p in (p_env, p_engine):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {
        "Donor_Patron": {
            "traits": {"charisma":[0.6,0.9],"authenticity":[0.4,0.8],"communication":[0.6,0.9],"strategy":[0.2,0.6],"temperament":[0.5,0.9]},
            "modifiers":{"risk_tolerance":[0.3,0.7],"generosity":[0.6,0.95],"media_savvy":[0.4,0.7]},
            "style":{"email":"warm","text":"brief","call":"animated","meeting":"collaborative"}
        }
    }

_PROFILES = _load_profiles()

def _rng_from_seed(seed: str) -> random.Random:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))

def _pick_range(rng: random.Random, lo: float, hi: float) -> float:
    if hi < lo: lo, hi = hi, lo
    return rng.uniform(lo, hi)

def _sample_block(rng: random.Random, ranges: Dict[str, Tuple[float,float]]) -> Dict[str,float]:
    return {k: round(_pick_range(rng, v[0], v[1]), 3) for k,v in ranges.items()}

def generate(seed: str, role: str, overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    arch = overrides.get("archetype") if overrides else None
    if not arch:
        role_map = {"donor":"Donor_Patron","coach":"Coach_Charismatic","journalist":"Journalist_Aggressive","admin":"Admin_Cautious"}
        arch = role_map.get(role.lower(), "Donor_Patron")
    profile = _PROFILES.get(arch) or list(_PROFILES.values())[0]

    rng = _rng_from_seed(seed + ":" + arch)
    traits = _sample_block(rng, profile["traits"])
    modifiers = _sample_block(rng, profile["modifiers"])
    style = dict(profile.get("style", {}))

    if overrides:
        traits.update(overrides.get("traits", {}))
        modifiers.update(overrides.get("modifiers", {}))
        style.update(overrides.get("style", {}))

    return {"id": seed, "archetype": arch, "seed": seed, "traits": traits, "modifiers": modifiers, "style": style}

def _clamp(x: float, lo: float, hi: float) -> float:
    return hi if x > hi else lo if x < lo else x

def donor_propensity(persona: Dict[str, Any], school_sentiment: float, prestige: float) -> float:
    gen = float(persona["modifiers"].get("generosity", 0.5))
    cha = float(persona["traits"].get("charisma", 0.5))
    sent = _clamp(float(school_sentiment), -1.0, 1.0)
    pre = _clamp(float(prestige) / 100.0, 0.0, 1.0)
    p = 0.45*gen + 0.25*cha + 0.2*max(0.0, sent) + 0.1*pre
    return _clamp(p, 0.05, 0.95)

def interaction_stance(persona: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    intensity = float(context.get("intensity", 0.0))
    temp = float(persona["traits"].get("temperament", 0.5))
    comm = float(persona["traits"].get("communication", 0.5))
    strat = float(persona["traits"].get("strategy", 0.5))
    risk_tol = float(persona["modifiers"].get("risk_tolerance", 0.5))

    tscore = (0.6*temp + 0.4*(0.5 + 0.5*intensity)) - 0.5
    tone = "positive" if tscore > 0.1 else "negative" if tscore < -0.1 else "neutral"

    energy_score = 0.5*abs(intensity) + 0.5*comm
    energy = "high" if energy_score > 0.66 else "low" if energy_score < 0.33 else "medium"

    risk = _clamp(0.6*risk_tol + 0.4*(1.0-strat), 0.0, 1.0)

    return {"tone": tone, "energy": energy, "risk": round(risk, 3)}

def style_for_channel(persona: Dict[str, Any], channel: str) -> str:
    return str(persona.get("style", {}).get(channel, "neutral"))
