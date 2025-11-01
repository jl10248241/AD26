# Changelog — v17.8 (2025-10-29)

### Added
- **INBOX index**: automatic logs/INBOX/index.csv writing on each emit.
- **Backfill tool**: 	ools/inbox_build_index.py --rebuild to regenerate index from existing packets.
- **Urgency derivation**: INFO / WARN / URGENT from explicit fields or keyword heuristic.
- **Urgency badges**: [ ], [!], [!!!] embedded in packets and shown in UI.
- **CLI viewer upgrades**: 	ools/ui_mock.py shows badges, color, and a varied sentiment line.
- **Viewer filters**: --role, --limit, --since.
- **Docs**: this changelog + project status.

### Changed
- **Bridge** (engine/src/v17_8/communication_bridge.py):
- Derives urgency at write time; attaches urgency_badge.
- Self-test CLI writes samples with --selftest --inbox.
- **Developer experience**:
- Pre-commit hook runs scripts/Validate-Workspace.ps1.
- .gitignore expanded to exclude logs, archives, and caches.

### Fixed
- Canonical config root respected: engine/config.

### Migration Notes
- If you have older packets, run:


python tools/inbox_build_index.py --inbox logs/INBOX --rebuild

- If your console shows odd glyphs, disable ANSI:


="1"

