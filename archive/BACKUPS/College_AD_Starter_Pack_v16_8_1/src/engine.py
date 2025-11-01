# engine.py — DBS_v1 + time-step invariant updates
# -------------------------------------------------
# What’s new:
#  - Time-step normalization (daily/weekly/biweekly/4-week supported)
#  - Exact pull toward moving baseline (Anchor + Cultivation + Era)
#  - Gravity scales with dt; per-week guardrail; base_decay off (DBS replaces it)
#  - Back-compat: if DBS files missing, anchor-only fallback

from models import Coach
import math
from loaders import load_trait_components
from pathlib import Path
import json

# ---- Trait components (unchanged) ----
TC = load_trait_components()
ALPHA = float(TC.get("meta", {}).get("alpha", 0.35))

def clamp01(x: float) -> float:
    return max(0.0, min(100.0, x))

def softcap(x: float) -> float:
    return 90 + (x - 90) * (1 / (1 + math.e ** ((x - 90) / 4))) if x > 90 else x

# ---- Context overrides (unchanged) ----
def apply_context_overrides(G, active, contexts_cfg):
    if not active:
        return G
    G2 = {k: v.copy() for k, v in G.items()}
    ctxs = contexts_cfg.get("contexts", {}) if isinstance(contexts_cfg, dict) else {}
    for ctx_id in active:
        spec = ctxs.get(ctx_id)
        if not spec:
            continue
        for ov in spec.get("gravity_overrides", []):
            s, t, d = ov["source"], ov["target"], ov["delta"]
            G2.setdefault(s, {})[t] = G2.get(s, {}).get(t, 0.0) + d
    return G2

# ---- DBS config (safe/optional) ----
_DBS_PATH = Path(__file__).resolve().parents[1] / "dbs" / "DBS_v1_Package"
_DBS_PRESENT = (_DBS_PATH / "dbs_config.json").exists() and (_DBS_PATH / "era_waterline.json").exists()
if _DBS_PRESENT:
    with open(_DBS_PATH / "dbs_config.json", "r") as _f:
        _DBS_CFG = json.load(_f)
    with open(_DBS_PATH / "era_waterline.json", "r") as _f:
        _ERA_CFG = json.load(_f)
    _DBS_DECAY = float(_DBS_CFG.get("decay_default", 0.02))  # per-week rate
    _CLAMP_MIN = float(_DBS_CFG.get("clamp", {}).get("min", 0.0))
    _CLAMP_MAX = float(_DBS_CFG.get("clamp", {}).get("max", 100.0))
else:
    _DBS_CFG, _ERA_CFG = {}, {}
    _DBS_DECAY = 0.0
    _CLAMP_MIN, _CLAMP_MAX = 0.0, 100.0

def _ensure_dbs_vectors(coach: Coach):
    keys = list(coach.traits.keys())
    if not hasattr(coach, "cultivation") or not isinstance(coach.cultivation, dict):
        coach.cultivation = {k: 0.0 for k in keys}
    else:
        for k in keys: coach.cultivation.setdefault(k, 0.0)
    if not hasattr(coach, "era_waterline") or not isinstance(coach.era_waterline, dict):
        coach.era_waterline = {k: 0.0 for k in keys}
    else:
        for k in keys: coach.era_waterline.setdefault(k, 0.0)

# ---- Subtrait blending (unchanged) ----
def _blend_subtraits_into_trait(coach: Coach, trait: str):
    st = getattr(coach, "subtraits", {}).get(trait)
    if not st: 
        return
    weights = TC[trait]["weights"]
    composite = 0.0
    for name, w in weights.items():
        composite += w * st.get(name, coach.traits.get(trait, 50.0))
    coach.traits[trait] = clamp01((1 - ALPHA) * coach.traits.get(trait, 50.0) + ALPHA * composite)

# ---- Exact pull toward baseline (stable across dt) ----
def _pull_exact(x: float, b: float, r_per_week: float, dt_weeks: float) -> float:
    # x(t+dt) = b + (x - b) * exp(-r * dt)
    k = math.exp(-max(0.0, r_per_week) * max(1e-9, dt_weeks))
    return b + (x - b) * k

# ---- Main weekly engine (now dt-aware) ----
def advance_week_trait_engine(coach: Coach, cfg, G, anchors, contexts, week: int):
    # --- time-step normalization ---
    days_per_week = float(cfg['core'].get('days_per_week', 7))
    tick_days     = float(cfg['core'].get('tick_days', 7))
    dt_weeks      = max(1e-9, tick_days / days_per_week)   # 1 day≈0.1429, 2wk=2.0, 4wk=4.0

    # 1) Subtrait blending
    for trait in list(coach.traits.keys()):
        if trait in TC and "weights" in TC[trait]:
            _blend_subtraits_into_trait(coach, trait)

    pre = coach.traits.copy()

    # 2) Context-aware gravity matrix
    active = getattr(coach, "active_contexts", [])
    G2 = apply_context_overrides(G, active, contexts)

    # 3) Inter-trait gravity (scaled by dt)
    accum = {k: 0.0 for k in coach.traits}
    for i in coach.traits:
        acc = 0.0
        for j in coach.traits:
            acc += G2[j].get(i, 0.0) * ((coach.traits[j] - 50) / 50)
        accum[i] = acc
    gscale = float(cfg['core']['gravity_scale']) * dt_weeks
    for i, acc in accum.items():
        coach.traits[i] = coach.traits[i] + acc * gscale

    # 4) Dynamic Baseline (DBS) exact pull
    A = anchors[coach.archetype]['anchor']
    k_anchor = float(coach.anchor_strength) if coach.anchor_strength is not None else float(cfg['core']['anchor_strength_default'])
    _ensure_dbs_vectors(coach)

    for i in coach.traits:
        if _DBS_PRESENT:
            baseline = float(A[i]) + float(coach.cultivation.get(i, 0.0)) + float(coach.era_waterline.get(i, 0.0))
            r = (_DBS_DECAY + 0.10 * k_anchor)   # per-week rate
            coach.traits[i] = _pull_exact(coach.traits[i], baseline, r, dt_weeks)
        else:
            # fallback: anchor-only, time-step scaled (exact)
            baseline = float(A[i])
            r = (0.10 * k_anchor)
            coach.traits[i] = _pull_exact(coach.traits[i], baseline, r, dt_weeks)

    # 5) Optional global decay is OFF with DBS (redundant).
    # If you insist, uncomment the following lines:
    # base_decay = float(cfg['core'].get('base_decay', 0.0))
    # if base_decay > 0:
    #     for i in coach.traits:
    #         coach.traits[i] -= base_decay * dt_weeks

    # 6) Per-week guardrail (prevents burst jumps on large dt)
    max_d_per_week = 1.0
    for tname in coach.traits:
        delta = coach.traits[tname] - pre[tname]
        limit = max_d_per_week * dt_weeks
        if delta >  limit: coach.traits[tname] = pre[tname] + limit
        if delta < -limit: coach.traits[tname] = pre[tname] - limit

    # 7) Clamp + softcap (unchanged)
    for i in coach.traits:
        coach.traits[i] = clamp01(softcap(coach.traits[i]))

    post = coach.traits.copy()
    delta = {k: post[k] - pre[k] for k in post}
    return pre, post, delta, active
