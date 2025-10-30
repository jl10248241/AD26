# Developer Notes (Updated for v17.8)

## CLI — Packet Emission
- Emit demo packets:


python -m engine.src.v17_8.communication_bridge --selftest --out-dir logs/INBOX

- Writes 3 packets (AAD/Coach/Board)
- Appends logs/INBOX/index.csv with 	imestamp,role,subject,urgency,file

## CLI — View / Triage
- Basic:


python tools/ui_mock.py --inbox logs/INBOX --limit 10

- Filters:


--role AAD|Coach|Board
--since YYYY-MM-DD
--limit N

- Color control:


="1" # disable ANSI colors (Windows fallback)


## Index Backfill


python tools/inbox_build_index.py --inbox logs/INBOX --rebuild


## Guardrails
- Validate structure:


powershell -ExecutionPolicy Bypass -File scripts\Validate-Workspace.ps1

- Pre-commit hook: blocks commits if validation fails.

## Conventions
- Configs: engine/config/**
- Inbox:   logs/INBOX/ (JSON packets + index.csv)
- No /configs/ folder at root (forbidden).
