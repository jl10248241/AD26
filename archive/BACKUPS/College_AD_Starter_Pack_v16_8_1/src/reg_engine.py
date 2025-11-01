# reg_engine.py — Drop-in for your reg_catalog schema (time-step aware, baked rules)
# ---------------------------------------------------------------------------------
# Supports your fields:
#  id, category, trigger_chance, weight, intensity{min,max}, persistence_weeks{min,max},
#  repeatable, cooldown_weeks, targets, eligibility{...}, effects[ ... ].
#
# Effects supported (as in your JSON):
#  - type: "trait_delta"  (who:"Coach", trait:"...", subtrait:"...", formula:"python expr using 'intensity'")
#  - type: "finance"      (who:"School", donor_yield_mul:"expr")
#  - type: "sentiment"    (who:"School", delta:"expr")
#  - type: "media_heat"   (who:"School", delta:"expr")
#  - type: "context_apply"(who:"Coach", context:"Name", weeks:"persistence")
#
# Baked mechanics:
#  - Time-step aware: trigger probability scales as p_dt = 1 - (1 - p_week) ** dt_weeks
#  - Intensity is uniform between [min,max] per fire; formula evaluated with safe eval
#  - Persistence tracked per-coach-per-event; remaining_weeks -= dt_weeks each tick
#  - Cooldown tracked per-coach-per-event; remaining_cooldown -= dt_weeks
#  - "trait_delta" applies to subtraits (coach.subtraits[trait][subtrait]) and is dt-scaled
#  - Also writes a small visible nudge into coach.traits[trait] if present (optional but handy)
#  - "context_apply weeks:'persistence'" = use the sampled persistence duration
#
# Engine state fields used/created on objects:
#   coach._reg_cooldowns: {event_id: remaining_weeks}
#   coach._reg_persist:   [{event_id, remaining_weeks, effects, intensity, context}]
#   coach.subtraits:      {Trait: {Subtrait: value}}
#   world fields used: world['Sentiment'], world['MediaHeat'], world['DonorYieldMul'] (init if missing)
#
# Call each tick (BEFORE trait engine):
#   logs = advance_reg_tick(coaches, world, cfg, reg_catalog, rng, week)

from __future__ import annotations
from typing import Any, Dict, List, Optional
import math, random

# -----------------------------
# Time step helpers
# -----------------------------

def _dt_weeks(cfg: Dict[str, Any]) -> float:
    days_per_week = float(cfg.get("core", {}).get("days_per_week", 7))
    tick_days     = float(cfg.get("core", {}).get("tick_days", 7))
    return max(1e-9, tick_days / days_per_week)

def _prob_dt_from_week(p_week: float, dt_weeks: float) -> float:
    # “probability this tick” from weekly probability under independence
    p_week = max(0.0, min(1.0, float(p_week)))
    return 1.0 - (1.0 - p_week) ** dt_weeks

# -----------------------------
# Safe evaluation for formulas
# -----------------------------

_ALLOWED_FUNCS = {"abs": abs, "min": min, "max": max}
def _eval_expr(expr: str, *, intensity: float) -> float:
    # Safe-ish eval limited to arithmetic + allowed funcs + 'intensity'
    return float(eval(expr, {"__builtins__": {}}, {"intensity": float(intensity), **_ALLOWED_FUNCS}))

# -----------------------------
# Eligibility checks (baked; extend as needed)
# -----------------------------

def _eligible(coach: Any, world: Dict[str, Any], elig: Optional[Dict[str, Any]]) -> bool:
    if not elig:
        return True
    # Prestige gate (prefer world-level; fall back to coach.school.prestige, then ok)
    pmin = elig.get("prestige_min", None)
    if pmin is not None:
        prestige = world.get("Prestige", None)
        if prestige is None:
            prestige = getattr(getattr(coach, "school", None), "prestige", None)
        if prestige is not None and prestige < float(pmin):
            return False
    # Example: 'auth_max' — try coach Authenticity trait or subtrait aggregate
    amax = elig.get("auth_max", None)
    if amax is not None:
        auth_val = 0.0
        # try trait
        if hasattr(coach, "traits") and "Authenticity" in coach.traits:
            auth_val = float(coach.traits["Authenticity"])
        # try subtrait Integrity under Authenticity (if present)
        if hasattr(coach, "subtraits"):
            st = coach.subtraits.get("Authenticity", {})
            auth_val = max(auth_val, float(st.get("Integrity", 0.0)))
        if auth_val > float(amax):
            return False
    return True

# -----------------------------
# Ensure state containers
# -----------------------------

def _ensure_state(world: Dict[str, Any], coach: Any) -> None:
    if not hasattr(coach, "_reg_cooldowns"):
        coach._reg_cooldowns = {}  # {event_id: remaining_weeks}
    if not hasattr(coach, "_reg_persist"):
        coach._reg_persist = []    # list of dicts with remaining_weeks, effects, intensity, context
    if not hasattr(coach, "subtraits") or not isinstance(coach.subtraits, dict):
        coach.subtraits = {}
    # handy world meters
    world.setdefault("Sentiment", 0.0)
    world.setdefault("MediaHeat", 0.0)
    world.setdefault("DonorYieldMul", 1.0)

# -----------------------------
# Apply immediate effects
# -----------------------------

def _apply_trait_delta(coach: Any, trait: str, subtrait: str, expr: str, intensity: float, dt: float, log: Dict[str, Any]) -> None:
    _ = coach.subtraits.setdefault(trait, {})
    delta = _eval_expr(expr, intensity=intensity) * dt
    _[subtrait] = float(_.get(subtrait, 0.0)) + delta
    # Optional: nudge visible parent trait if it exists (keeps UX tangible)
    if hasattr(coach, "traits") and trait in coach.traits:
        coach.traits[trait] = float(coach.traits[trait]) + 0.1 * delta  # small bleed-in
    log.setdefault("trait_deltas", []).append({"trait": trait, "subtrait": subtrait, "delta": delta})

def _apply_finance(world: Dict[str, Any], expr_mul: str, intensity: float, dt: float, log: Dict[str, Any]) -> None:
    mul = _eval_expr(expr_mul, intensity=intensity)  # multiplier (not dt-scaled)
    world["DonorYieldMul"] = float(world.get("DonorYieldMul", 1.0)) * float(mul)
    log.setdefault("finance", []).append({"DonorYieldMul_x": mul})

def _apply_sentiment(world: Dict[str, Any], expr: str, intensity: float, dt: float, log: Dict[str, Any]) -> None:
    d = _eval_expr(expr, intensity=intensity) * dt
    world["Sentiment"] = float(world["Sentiment"]) + d
    log.setdefault("sentiment", 0.0)
    log["sentiment"] += d

def _apply_media_heat(world: Dict[str, Any], expr: str, intensity: float, dt: float, log: Dict[str, Any]) -> None:
    d = _eval_expr(expr, intensity=intensity) * dt
    world["MediaHeat"] = float(world["MediaHeat"]) + d
    log.setdefault("media_heat", 0.0)
    log["media_heat"] += d

def _apply_context(coach: Any, context: str, weeks: float, log: Dict[str, Any]) -> None:
    # Record an active timed context on the coach
    # Store as a special persist entry so the rest of your engine can read coach.active_contexts if needed.
    coach._reg_persist.append({
        "event_id": f"CTX::{context}",
        "remaining_weeks": float(weeks),
        "effects": None,
        "intensity": 0.0,
        "context": context
    })
    log.setdefault("contexts_applied", []).append({"context": context, "weeks": weeks})

# -----------------------------
# Per-tick persistence re-application
# -----------------------------

def _tick_persistence(coach: Any, dt: float, logs: List[Dict[str, Any]]) -> None:
    keep = []
    for eff in getattr(coach, "_reg_persist", []):
        eff["remaining_weeks"] = float(eff.get("remaining_weeks", 0.0)) - dt
        if eff["remaining_weeks"] > 1e-6:
            # if this is a context-only entry, nothing to re-apply numerically here;
            # your trait engine reads the context name if needed
            if eff.get("effects"):
                # If you later add lingering numeric effects, you can re-apply here.
                pass
            keep.append(eff)
        # else drop (expired)
    coach._reg_persist = keep

# -----------------------------
# Cooldown decrement
# -----------------------------

def _decrement_cooldowns(coach: Any, dt: float) -> None:
    cds = getattr(coach, "_reg_cooldowns", {})
    expired = []
    for k, rem in cds.items():
        newv = float(rem) - dt
        if newv <= 0:
            expired.append(k)
        else:
            cds[k] = newv
    for k in expired:
        cds.pop(k, None)
    coach._reg_cooldowns = cds

# -----------------------------
# Main entry
# -----------------------------

def advance_reg_tick(coaches: List[Any],
                     world: Dict[str, Any],
                     cfg: Dict[str, Any],
                     reg_catalog: List[Dict[str, Any]],
                     rng: Optional[random.Random],
                     week: int) -> List[Dict[str, Any]]:

    rng = rng or random.Random()
    dt = _dt_weeks(cfg)
    logs: List[Dict[str, Any]] = []

    # Decay/expire persistence & cooldowns first
    for coach in coaches:
        _ensure_state(world, coach)
        _tick_persistence(coach, dt, logs)
        _decrement_cooldowns(coach, dt)

    # Try each catalog entry
    for ev in reg_catalog or []:
        ev_id    = ev.get("id", "EV")
        p_week   = float(ev.get("trigger_chance", 0.0))
        p_tick   = _prob_dt_from_week(p_week, dt)
        targets  = ev.get("targets", ["Coach"])
        elig     = ev.get("eligibility", None)
        cooldown_weeks = float(ev.get("cooldown_weeks", 0.0))
        repeatable = bool(ev.get("repeatable", True))
        # intensity sample
        imin, imax = float(ev.get("intensity", {}).get("min", 0.0)), float(ev.get("intensity", {}).get("max", 0.0))

        # Who can be targeted (simple version: all coaches; you can refine selection later)
        target_coaches = list(coaches) if ("Coach" in targets) else []
        target_school  = ("School" in targets)  # world-level effects

        # Roll once per eligible coach (common sports-sim approach)
        for coach in target_coaches:
            if not _eligible(coach, world, elig):
                continue
            _ensure_state(world, coach)

            # Honor cooldown
            if ev_id in coach._reg_cooldowns:
                continue

            if rng.random() <= p_tick:
                # Sample intensity
                intensity = rng.uniform(imin, imax)

                # Decide persistence duration
                pmin = float(ev.get("persistence_weeks", {}).get("min", 0.0))
                pmax = float(ev.get("persistence_weeks", {}).get("max", 0.0))
                persistence_weeks = rng.uniform(pmin, pmax) if pmax > 0.0 else 0.0

                # Apply EFFECTS
                log = {"week": week, "id": ev_id, "coach": getattr(coach, "name", None), "intensity": intensity}

                for eff in (ev.get("effects") or []):
                    etype = eff.get("type")
                    who   = eff.get("who", "Coach")

                    if etype == "trait_delta" and who == "Coach":
                        _apply_trait_delta(
                            coach,
                            trait   = eff.get("trait", "Unknown"),
                            subtrait= eff.get("subtrait", "Default"),
                            expr    = eff.get("formula", "0"),
                            intensity = intensity,
                            dt     = dt,
                            log    = log
                        )

                    elif etype == "finance" and who == "School" and target_school:
                        _apply_finance(world, eff.get("donor_yield_mul", "1"), intensity, dt, log)

                    elif etype == "sentiment" and who == "School" and target_school:
                        _apply_sentiment(world, eff.get("delta", "0"), intensity, dt, log)

                    elif etype == "media_heat" and who == "School" and target_school:
                        _apply_media_heat(world, eff.get("delta", "0"), intensity, dt, log)

                    elif etype == "context_apply" and who == "Coach":
                        # weeks:"persistence" means: use sampled persistence_weeks
                        weeks_expr = eff.get("weeks", "persistence")
                        if weeks_expr == "persistence":
                            weeks_val = persistence_weeks
                        else:
                            # allow a numeric or expression like "max(2, intensity*4)"
                            try:
                                weeks_val = _eval_expr(str(weeks_expr), intensity=intensity)
                            except Exception:
                                weeks_val = float(weeks_expr)
                        if weeks_val > 0:
                            _apply_context(coach, eff.get("context", "Context"), weeks_val, log)

                # Register cooldown
                if cooldown_weeks > 0.0:
                    coach._reg_cooldowns[ev_id] = cooldown_weeks

                # Register persistence “slot” for this event (context-only is handled above;
                # you can add numeric lingering effects later if desired)
                if persistence_weeks > 0.0:
                    coach._reg_persist.append({
                        "event_id": ev_id,
                        "remaining_weeks": persistence_weeks,
                        "effects": None,     # placeholder for numeric lingering maps if you add them later
                        "intensity": intensity,
                        "context": None
                    })

                logs.append(log)

        # Also allow world-only fires on this event (once per tick)
        if target_school and rng.random() <= p_tick:
            intensity = rng.uniform(imin, imax)
            log = {"week": week, "id": ev_id, "coach": None, "intensity": intensity}
            for eff in (ev.get("effects") or []):
                etype = eff.get("type")
                if etype == "finance":
                    _apply_finance(world, eff.get("donor_yield_mul", "1"), intensity, dt, log)
                elif etype == "sentiment":
                    _apply_sentiment(world, eff.get("delta", "0"), intensity, dt, log)
                elif etype == "media_heat":
                    _apply_media_heat(world, eff.get("delta", "0"), intensity, dt, log)
            logs.append(log)

    return logs
