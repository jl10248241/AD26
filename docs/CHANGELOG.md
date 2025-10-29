# College AD — Change Log

*Last updated: 2025-10-29*

---

## 📘 Purpose

Tracks incremental development, feature additions, and fixes across all versions of **College AD**. Each section summarizes system-level, gameplay, and engine-level changes to ensure continuity and regression traceability.

---

## 🧩 Version History

### v17.7 — Unified Communication Bridge (Stable)

**Release Date:** 2025-10-29
**Type:** Stable Build

**Highlights:**

* Integrated donor memory/decay lifecycle and pledge stipulations modules.
* Added unified communication bridge with multi-channel output (email, text, meeting).
* CLI inbox viewer (`tools/ui_mock.py`) implemented for rapid message preview.
* All logs and messages routed to standardized `/logs/INBOX/` path.
* `.env` now defines `CONFIG_DIR`, `LOG_DIR`, `INBOX_DIR`.

**Technical Improvements:**

* Robust `run_tick.py` with modular hooks for donor, pledge, and bridge systems.
* Improved finance logging and sentiment tracking.
* Added auto-alignment scripts (`Align-Workspace.ps1`, `Smoke-Verify.ps1`).
* Created canonical `DEVELOPER_NOTES.md` and auto structure snapshots.

**Known Issues:**

* No real-time threading between channels yet (planned v18).
* Limited donor sentiment visualization.

---

### v17.6 — Personality Core + Finance/Prestige

**Release Date:** 2025-10-15
**Type:** Stable Build

**Highlights:**

* Personality Core introduced for AAD and Coach archetypes.
* Finance + prestige subsystem refined with sentiment balancing.
* Donor report integration into `excel_bridge.py`.

**Technical Improvements:**

* Stable schema for `FINANCE_LOG.csv` and `DONOR_LEDGER.csv`.
* Enhanced regression hooks for simulation engine.

**Known Issues:**

* Communication systems placeholder only.
* Missing decay curve model for donors (added in 17.7).

---

### v17.5 — Trait Engine & Core Simulation Upgrade

**Release Date:** 2025-09-28
**Type:** Stable Build

**Highlights:**

* Trait engine complete: personality-to-performance loop functioning.
* Weekly tick cycle implemented with event-based finance and prestige updates.
* Added support for dynamic REG catalog loading.

**Technical Improvements:**

* Modularized `advance_week_trait_engine()` and `advance_reg_tick()`.
* CSV auto-header verification for world events.

---

### v17.2 — Unified Workspace Setup

**Release Date:** 2025-08-10
**Type:** Setup/Infrastructure Build

**Highlights:**

* Transition to unified workspace folder (`College_AD_Unified_Workspace_Blank_v17.2`).
* `.env` environment configuration introduced.
* Initial documentation and version tagging templates created.

**Technical Improvements:**

* First use of PowerShell setup scripts.
* Introduced modular config resolution with fallback behavior.

---

## 🔮 Planned (v17.8 → v18 Roadmap)

### v17.8 — Bridge+UX Enhancements (Pre-Alpha)

* ANSI color-coded urgency in CLI.
* Real-time donor sentiment pulse integration into bridge packets.
* Threaded conversation mockup for Board/AAD.
* Expanded logging and INBOX metadata indexing.

### v18 — Interactive UI & Live Simulation

* Replace CLI inbox with graphical prototype.
* Add phone-call scenes and AI-driven donor dialogues.
* True cross-channel message threading.
* Visual dashboards for donor memory and pledge analytics.

---

*End of CHANGELOG.md — maintain at every build checkpoint.*
