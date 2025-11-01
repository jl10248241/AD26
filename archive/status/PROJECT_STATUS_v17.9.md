
# Project Status — v17.9 (2025-10-29)

## Summary
v17.9 focuses on making the sim playable & readable: plain-language UI strings, a real inbox, donor ledger mirroring, and finance/sentiment validation.

## Key Changes
- `ui_strings.py`: Friendly labels & summaries (donor/coach/inbox).
- `communication_bridge.py`: Emits `/logs/INBOX/*.json` **and** mirrors pledge_* to `/logs/DONOR_LEDGER.csv`.
- `ui_inbox_cli.py`: Read-only inbox list/detail, filters, watch mode.
- `finance_validator.py`: Validates `FINANCE_LOG.csv`, writes `docs/FINANCE_TRENDS.md`.

## Integration
- `run_tick.py` now prefers canonical `communication_bridge` and can call `finance_validator` each tick (add the tail patch).

## Files to Keep
- `/engine/src/ui_strings.py`
- `/engine/src/communication_bridge.py`
- `/engine/src/ui_inbox_cli.py`
- `/engine/src/finance_validator.py`
- `/logs/INBOX/`, `/logs/DONOR_LEDGER.csv`, `/logs/FINANCE_LOG.csv`
- `/docs/FINANCE_TRENDS.md`

## Next
- v18: Comms v2 (compose/reply), richer donor lifecycle states, and GUI pass.
