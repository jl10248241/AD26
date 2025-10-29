# College AD — Developer Notes

*Last updated: 2025-10-29*

---

## 🧭 Purpose

Defines the **canonical developer workflow** and **project directory structure** for all College AD builds (v17.7 → v18). Ensures consistency, maintainability, and clarity across all development environments.

---

## 🔧 Canonical File Structure (v17.7 → v18 Unified Layout)

```
College_AD/
 ├─ engine/
 │   ├─ src/
 │   │   ├─ v17_7/
 │   │   │   ├─ donor_memory.py
 │   │   │   ├─ pledge_stipulations.py
 │   │   │   ├─ communication_bridge.py
 │   │   │   ├─ ui_mock.py
 │   │   │   └─ __init__.py
 │   │   ├─ reg_engine.py
 │   │   ├─ engine.py
 │   │   ├─ run_tick.py
 │   │   └─ ...
 │   ├─ config/
 │   │   ├─ reg_catalog.json
 │   │   ├─ reg_weights.json
 │   │   ├─ trait_components.json
 │   │   ├─ trait_gravity.json
 │   │   ├─ ad_archetypes.json
 │   │   ├─ donor_decay.json
 │   │   ├─ pledge_rules.json
 │   │   └─ bridge_filters.json
 │   ├─ logs/              # transient (dev-only)
 │   └─ dbs/
 │
 ├─ tools/
 │   ├─ ui_mock.py
 │   ├─ paths_example.py
 │   └─ ...
 │
 ├─ scripts/
 │   ├─ Setup-Workspace.ps1
 │   ├─ Align-Workspace.ps1
 │   ├─ Smoke-Verify.ps1
 │   └─ ...
 │
 ├─ logs/
 │   ├─ INBOX/
 │   ├─ FINANCE_LOG.csv
 │   ├─ DONOR_LEDGER.csv
 │   └─ ...
 │
 ├─ docs/
 │   ├─ PROJECT_STATUS_v17.7.md
 │   ├─ CHANGELOG.md
 │   ├─ DEVELOPER_NOTES.md   ← (this file)
 │   └─ _structure_snapshots/
 │
 ├─ data/
 │   ├─ anchors.json
 │   ├─ world.json
 │   └─ ...
 │
 ├─ Archive/
 │   ├─ College_AD_v17.6_Backup/
 │   └─ ...
 │
 ├─ .env
 ├─ requirements.txt
 └─ README.md
```

---

## ⚙️ Environment Variables (`.env`)

```
CONFIG_DIR=engine/config
LOG_DIR=logs
INBOX_DIR=logs/INBOX
```

* Never hard-code absolute paths in Python; always resolve via these ENV keys.
* Add new ENV keys only through `.env` or setup scripts.

---

## 🧩 Developer Policy

| Category       | Standard                                                            |
| -------------- | ------------------------------------------------------------------- |
| **Configs**    | All JSON configs live in `engine/config/`.                          |
| **Logs**       | All CSVs + Inbox JSONs go under root `logs/`.                       |
| **Versioning** | New systems (v18+) live in their own folder `engine/src/v18/`.      |
| **Archive**    | Only historical zips or snapshots — no live code.                   |
| **Tests**      | Run `scripts/Smoke-Verify.ps1` before any commit.                   |
| **Cleanup**    | Run `scripts/Align-Workspace.ps1` weekly to auto-realign structure. |

---

## 🧠 Workflow Summary

1. **Before coding:** Run `Align-Workspace.ps1` → fixes folders & updates `.env`.
2. **During development:** Work only inside `engine/src/` and `engine/config/`. Keep all temp output in `logs/`.
3. **Before commit or build:** Run `Smoke-Verify.ps1`, review `logs/INBOX` output via `tools/ui_mock.py`, then tag milestone → update `docs/CHANGELOG.md`.

---

## 🗂 Automatic Structure Snapshots

Each session can output a tree snapshot to `docs/_structure_snapshots/structure_<timestamp>.txt`.

Add this snippet to the end of `scripts/Align-Workspace.ps1`:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$structureFile = "$PSScriptRoot\..\docs\_structure_snapshots\structure_$timestamp.txt"
New-Item -ItemType Directory -Force -Path (Split-Path $structureFile) | Out-Null
tree /f /a > $structureFile
Write-Host "📁 Structure snapshot saved to: $structureFile"
```

---

## 🧾 Git & Version Control

* Initialize git at project root.
* `.gitignore` minimum:

  ```
  __pycache__/
  *.pyc
  logs/
  *.csv
  *.xlsx
  /Archive/
  ```
* Commit each milestone as `v17.7_stable`, `v18_prealpha`, etc.

---

## 📦 Release Workflow

1. Run `Align-Workspace.ps1`
2. Run `Smoke-Verify.ps1`
3. Export build as zip → `College_AD_v17.7_Stable.zip`
4. Move zip → `/Archive/`

Config Merge Policy

engine/config is always the canonical config folder.

New configs from /configs/ (e.g., bridge, pledge, donor) must be migrated there, not duplicated.

Conflicts (reg_weights.json, trait_components.json) should be version-controlled and merged by timestamp.

Old /configs/ folders are archived under /Archive/configs_backup_<build>/.

“All documentation lives under /docs/. The /engine/docs/ folder is forbidden for live builds.”


Per-module notes go in docs/modules/<module>.md (if needed).


Milestone status files use docs/PROJECT_STATUS_v<ver>.md only (no templates kept once shipped).


If you want, I can also generate a tiny validator script that fails CI when /engine/docs/ or docs/*_TEMPLATE.md exists—just say the word.
---

*End of Developer Notes — maintain this structure for every build checkpoint.*
