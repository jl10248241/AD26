# College AD — Project Status Report (v17.7)

*Compiled: 2025-10-28 — Developer Build Summary*

---

## 🧭 Overview

v17.7 delivers first-pass systems for **donor memory/decay**, **pledge stipulations**, and a **unified communications bridge** with a CLI inbox preview. This build completes the gameplay plumbing needed to feed AAD/Coach/Board messages from real simulation events and establishes test fixtures for UI/UX.

---

## ✅ What’s Included in v17.7

### Core Systems

* **Donor Memory / Decay** (`engine/v17_7/donor_memory.py`)

  * Models natural engagement fade over time with configurable half-life per donor archetype.
  * Weekly update blends: prior_state → gravity → recent_interactions → event_pulses.
  * Outputs trust/leverage deltas to donor ledger and sentiment hooks.

* **Pledge Stipulations Lifecycle** (`engine/v17_7/pledge_stipulations.py`)

  * Tracks pledges across: `promised → pending → received / lapsed`.
  * Supports conditions (earmark, timeline, matching funds, naming rights).
  * Emits world events when milestones hit or deadlines miss.

* **Unified Communication Bridge** (`engine/v17_7/communication_bridge.py`)

  * Converts world events + donor/coach/board state into **Message Packets**.
  * Writers for channels: `email`, `text`, `meeting` with a common envelope.
  * Pluggable filters for urgency, audience, and narrative tone.

* **CLI Inbox Preview** (`tools/ui_mock.py`)

  * Renders message feed from `logs/INBOX/*.json`.
  * Supports quick filters: `--AAD`, `--Coach`, `--Board`, `--urgent`.
  * Designed to inform the later UI prototype (v18+).

### File Outputs & Logs

* **Inbox Samples:** `logs/INBOX/*.json` (AAD / Coach / Board profiles).
* **Donor Ledger (extended):** `logs/DONOR_LEDGER.csv` (now includes memory/stipulation events).
* **Finance Log (compatible):** `logs/FINANCE_LOG.csv` (no schema change; consumed by Analyzer).

---

## 🧪 Self-Test & Verification

Run any of the following from project root. All paths are relative and robust to CWD:

```bash
# 1) Donor memory/decay unit suite
python -m engine.v17_7.donor_memory --selftest

# 2) Pledge stipulations lifecycle checks
python -m engine.v17_7.pledge_stipulations --selftest

# 3) Communication bridge smoke + inbox fixtures
python -m engine.v17_7.communication_bridge --selftest --emit-samples

# 4) CLI inbox preview (inspect output)
python tools/ui_mock.py --role AAD --urgent
python tools/ui_mock.py --role Coach --since 4w
```

**Pass Criteria**

* Decay curves clamp within design bounds (no weekly |Δ| > 1.0 unless event pulse).
* Stipulations transition cleanly with auditable timestamps.
* Inbox samples generated for AAD/Coach/Board with valid envelopes.

---

## ⚙️ Integration Notes

### Engine Hooks

* `run_tick.py` now imports `donor_memory.tick_update()` and `pledge_stipulations.tick_update()` early in the finance/donor phase.
* `reg_engine` raises donor + prestige pulses that the bridge ingests into messages on tick end.

### Configuration

* `config/donor_decay.json` — per-archetype half-life, ceiling/floor clamps, and pulse weights.
* `config/pledge_rules.json` — allowable conditions and defaults for transitions.
* `config/bridge_filters.json` — channel routing & urgency thresholds.

### Directory Layout

```
engine/
  v17_7/
    donor_memory.py
    pledge_stipulations.py
    communication_bridge.py
tools/
  ui_mock.py
logs/
  INBOX/
  DONOR_LEDGER.csv
  FINANCE_LOG.csv
config/
  donor_decay.json
  pledge_rules.json
  bridge_filters.json
```

---

## 🔎 Developer Tips

* **Tuning decay:** Raise/lower the half-life per archetype; watch the AAD’s language readability stay “plain-English” via the dialogue layer.
* **Stipulations:** Use `--backfill` to migrate legacy pledges; the tool will infer `promised_at` if missing.
* **Bridge:** Add `--dry-run` to validate envelopes without writing files.

---

## 🐞 Known Issues / Limits

* No real-time cross-channel threading yet (email↔text↔meeting). Planned in v18.
* Bridge currently writes flat JSON; pagination and pinning are deferred to UI.
* Edge case: overlapping pledge deadlines in the same week may produce duplicate reminders (guard coming in v17.7.1).

---

## 📌 Next (v18 Roadmap Preview)

* Wire bridge to **live** tick events (not just end-of-week rollups).
* Expand inbox to **filter / search / pin**, add conversation threading.
* Draft UI mock for **email/text/meeting** feed; introduce phone-call scenes.

---

## ✅ Checklist — What to Verify Before Shipping

* [ ] Selftests all green.
* [ ] `logs/INBOX/` contains AAD, Coach, and Board samples.
* [ ] Analyzer reads extended DONOR_LEDGER without schema errors.
* [ ] AAD dialogue surfaces plain-English summaries for trust/leverage.

---

*End of Report — v17.7 milestone*
