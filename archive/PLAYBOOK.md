# College AD — PLAYBOOK (v17.9)

## One-time
- `python -m engine.src.communication_bridge` → writes sample INBOX + DONOR_LEDGER

## Inbox
- List: `python -m engine.src.ui_inbox_cli`
- Only pledges: `python -m engine.src.ui_inbox_cli --only-pledges`
- Only last 3 days: `python -m engine.src.ui_inbox_cli --since 3`
- Open item #2 file: `python -m engine.src.ui_inbox_cli --open 2`
- Detail #3: `python -m engine.src.ui_inbox_cli --detail 3`
- Watch: `python -m engine.src.ui_inbox_cli --watch`

## Finance
- Validate: `python -m engine.src.finance_validator`
- Strict (nonzero exit if issues): `python -m engine.src.finance_validator --strict`
- School filter: `python -m engine.src.finance_validator --school "State U"`

## Donor Snapshot
- Build snapshot: `python -m engine.src.donor_snapshot`
- Filter donor name: `python -m engine.src.donor_snapshot --donor Mega`
- JSON out: `python -m engine.src.donor_snapshot --json`

## Tick (simulation)
- Your run should call `run_one_tick()`; after the patch, it auto-rebuilds:
  - `docs/FINANCE_TRENDS.md`
  - `docs/DONOR_SNAPSHOT.md`

## Logs
- Engine logs: `logs/engine.log`
- Inbox packets: `logs/INBOX/*.json`
- Donor ledger: `logs/DONOR_LEDGER.csv`
- Finance rows: `logs/FINANCE_LOG.csv`
