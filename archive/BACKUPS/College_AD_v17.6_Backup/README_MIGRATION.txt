College AD — One-Folder Migration Guide (Unified Workspace v17.2)
Date: 2025-10-27

Target Structure:
  College_AD_Unified_Workspace_v17.2/
    engine/        -> your old College_AD_Starter_Pack_v16_8_1 (copied here)
    configs/       -> JSON configs (replace placeholders)
    logs/          -> CSV outputs (stubs included)
    docs/          -> v1.1 setup + design + changelog
    snapshots/     -> milestone archives
    data/          -> seeds
    scripts/       -> Setup-Workspace.ps1
    tools/         -> paths_example.py
    .env

Steps:
1) Extract this zip where you want ONE working folder.
2) PowerShell:
   cd .\College_AD_Unified_Workspace_Blank_v17.2\scripts
   .\Setup-Workspace.ps1 -EnginePath "C:\COLLEGE_AD26\College_AD_Starter_Pack_v16_8_1"
3) Update your engine to use workspace-relative paths (see tools/paths_example.py).
4) Run the sim from: engine\excel_bridge.py
5) Logs will appear in: logs\
6) Keep docs in: docs\ for reference and archiving.
Rollback: Replace /engine with your archived v17.2 copy if needed.
