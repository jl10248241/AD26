
# DBS_v1 drop-in integration for College AD Engine (v17.2+)
# Applies dynamic baselines for Core Principles (CPs).
from typing import Dict

def clamp(x, lo, hi): 
    return max(lo, min(hi, x))

def update_dynamic_baseline(cp_name: str, anchor: float, cultivation: float, era_wl: float) -> float:
    return anchor + cultivation + era_wl

def step_cultivation(cp_name: str, cultivation: float, coaching_inputs: float, outcome_signals: float,
                     alpha: float, backslide_lambda: float, cap_abs: float) -> float:
    d = alpha * (coaching_inputs + outcome_signals) - backslide_lambda * (cultivation - 0.0)
    cultivation_new = clamp(cultivation + d, -cap_abs, cap_abs)
    return cultivation_new

def step_era_waterline(cp_name: str, era_wl: float, mu: float, region_mult: float, cap_abs: float) -> float:
    era_wl_new = era_wl + mu * region_mult
    era_wl_new = clamp(era_wl_new, -cap_abs, cap_abs)
    return era_wl_new

def step_core_principle(cp_val: float, baseline: float, effects: float, decay: float, clamp_min: float, clamp_max: float) -> float:
    # CP_{t+1} = CP_t + Effects - decay*(CP_t - Baseline_t)
    new_val = cp_val + effects - decay * (cp_val - baseline)
    return clamp(new_val, clamp_min, clamp_max)
