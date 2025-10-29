
# Dynamic Baseline System (DBS_v1) — Integration Notes

**Scope:** Replaces static trait gravity with a three-layer baseline per Core Principle (CP):
`Baseline = Anchor + Cultivation + EraWaterline`.

## Files
- `dbs_config.json` — plasticity α, cultivation caps, decay, backslide λ, clamps
- `era_waterline.json` — weekly μ drift, era caps, region overrides (hooks for CoL/culture)
- `dbs_engine_dropin.py` — reference functions for engine integration

## Update Sequence (per week, per CP)
1) `Cultivation <- step_cultivation(...)`
2) `EraWaterline <- step_era_waterline(...)`
3) `Baseline <- Anchor + Cultivation + EraWaterline`
4) `CP <- step_core_principle(CP, Baseline, Effects, decay)`
5) Traits recompute via existing `trait_components.json` weights.

## Defaults
- Decay: 0.02
- Backslide λ: 0.08
- Clamps: [-100, 100]

## Tuning Guidance
- Low-plasticity CPs: Honesty (α=0.10), Accountability (0.15) → small cultivation caps.
- Higher-plasticity CPs: Curiosity (0.45), SocialSavvy (0.40) → larger caps.
- Era drift μ typical range: 0.005–0.02 weekly; use regional multipliers sparingly.

## Unit Tests
- **Stability:** 250 weeks with no interventions keeps CP variance < 5 for low-α CPs.
- **Intervention:** Apply +1.0 weekly support on SocialSavvy for 20 weeks: CP increase 6–12.
- **Backslide:** Remove support → ~30–50% reversion over 12–20 weeks.
- **Era Drift:** With μ=0.015, SocialSavvy trend ≈ +3.9 over 5 years; respects era caps.
- **Clamp Safety:** Ensure CP, Baseline respect [-100,100]; Cultivation and Era stay within caps.

## Hooks for v17.5
- Region overrides tie into CoL and culture layers via FSPL.
- Add `context multipliers` so Effects scale post-scandal vs post-championship.
