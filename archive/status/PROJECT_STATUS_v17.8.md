# Project Status — v17.8 (2025-10-29)

## Summary
v17.8 focuses on communication clarity and auditability:
- INBOX packet indexing (index.csv)
- Urgency surfacing (badges + color)
- Sentiment pulse in viewer
- Guardrails: validator + pre-commit hook

## What shipped in v17.8
- **INBOX Index**: every emitted packet appends a row to logs/INBOX/index.csv (timestamp, role, subject, urgency, file).
- **Urgency**: packets carry urgency (INFO / WARN / URGENT) and urgency_badge ([ ], [!], [!!!]).
- **CLI Viewer**: 	ools/ui_mock.py shows badges in color (ANSI-safe), and a varied sentiment line (“Sentiment / Fan mood / Pulse / Crowd vibe / Temperature”).
- **Filters**: --role, --limit, --since in the viewer for quick triage.
- **Guardrails**: scripts/Validate-Workspace.ps1 + pre-commit hook prevent structure drift.

## Verified commands
- Emit sample packets:
python -m engine.src.v17_8.communication_bridge --selftest --inbox logs/INBOX
- View packets:
python tools/ui_mock.py --inbox logs/INBOX --limit 6
python tools/ui_mock.py --role Coach --since 2025-10-29

- Rebuild index from existing JSON:


python tools/inbox_build_index.py --inbox logs/INBOX --rebuild


## Open items (carry to v17.9)
- Role-aware phrasing packs for sentiment (AAD/Coach/Board).
- Optional “since minutes/hours” flags in viewer.
- Docs: user-facing quickstart (non-developer).

## Risks / Notes
- ANSI color can be disabled with NO_ANSI=1.
- Keep .env canonical (CONFIG_DIR=engine/config, LOG_DIR=logs, INBOX_DIR=logs/INBOX).
- Never reintroduce /configs/ (validator will block).

## Next milestones
- Tag release 17.8-final
- Branch 17.9/* for next feature set
