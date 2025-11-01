# \# TODO — v17.9 (Kickoff)

# 

# \## Goals

# \- Stabilize AAD \& comm\_auto policy toggles

# \- Tie Media Reach → Recruiting difficulty bands

# \- Weekly sim autopilot guardrails

# 

# ---

# 

# \## Task 1 — AAD \& Comm\_Auto Policy Sync (JSON-safe setters)

# \- \[ ] Verify `engine/config/aad\_policies.json` and `engine/config/comm\_auto\_policy.json`

# \- \[ ] Ensure boolean setters serialize to `true/false` (no stringy-bools)

# \- \[ ] Add CLI options to toggle common flags (enabled, allow\_autosend, require\_ack)

# \- \[ ] `selftest` confirms read→modify→write→read cycle parity

# 

# \*\*Files:\*\*  

# `engine/config/aad\_policies.json`, `engine/config/comm\_auto\_policy.json`, `engine/src/ui\_comm\_auto\_cli.py`

# 

# ---

# 

# \## Task 2 — Media Reach → Recruiting Difficulty

# \- \[ ] Read `engine/config/MEDIA\_REACH.json` in `recruiting\_influence.py`

# \- \[ ] Map zones → multipliers (Local/Regional/National)

# \- \[ ] Apply multiplier in recruiting probability pipeline

# \- \[ ] `selftest` prints banded examples + writes a short report

# 

# \*\*Files:\*\*  

# `engine/config/MEDIA\_REACH.json`, `engine/src/recruiting\_influence.py`, `engine/src/ui\_recruiting\_influence\_cli.py`

# 

# ---

# 

# \## Task 3 — Weekly Autopilot Guardrails

# \- \[ ] Add week bounds + state-file presence checks in `run\_tick.py`

# \- \[ ] On violation: log to `logs/engine.log` and halt tick

# \- \[ ] Smoke script covers both happy-path and fail-fast

# 

# \*\*Files:\*\*  

# `engine/src/run\_tick.py`, `engine/state/clock.json`, `docs/SMOKE\_v17.9.ps1`

# 

# ---

# 

# \## Verification

# \- \[ ] `python -m engine.src.ui\_comm\_auto\_cli --selftest --sync`

# \- \[ ] `python -m engine.src.ui\_recruiting\_influence\_cli --selftest --verbose`

# \- \[ ] `.\\docs\\SMOKE\_v17.9.ps1`  (PowerShell 5)



