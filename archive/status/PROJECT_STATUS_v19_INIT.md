# College AD — Project Status v19 Initialization  
**Date:** 2025-11-01  
**Build Name:** v19_INIT — “New Era Kickoff”  
**Author:** GPT-5 (Developer Partnered with Jason L.)

## Summary
v19 opens with the AI Relationship Core. Drop-ins provide PowerShell wrappers and Python modules to track trust/loyalty/respect between the AD and key NPCs. Rule #1 honored: no auto-created folders.

## Files Introduced (Task 1)
- `scripts\v19.Relationship-Core.ps1`
- `scripts\Session-Start_v19.ps1`
- `engine\src\relationship_core.py`
- `engine\src\ui_relationship_report.py`

## Quickstart
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\scripts\Session-Start_v19.ps1
Init-RelationshipCore
rel.apply -Subject Player_AD -Target Coach.HeadCoach -Effect meeting_good -Intensity 12 -Tone positive
rel.show
rel.tick -Weeks 1
rel.md
```
