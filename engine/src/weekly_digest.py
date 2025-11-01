# engine/src/weekly_digest.py — writes docs/WEEKLY_DIGEST.md from a tick result
from __future__ import annotations
from typing import Dict, Any
from .config_paths import DOCS

def write_weekly_digest(result: Dict[str, Any]) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    out = DOCS / "WEEKLY_DIGEST.md"

    week = result.get("week_ended", "?")
    inbox_n = len(result.get("inbox_files", []))
    media_file = result.get("media_file", "-")
    nudges = result.get("nudges", {})
    fan = nudges.get("fan_energy", {})
    mor = nudges.get("coach_morale", {})

    lines = []
    if not out.exists():
        lines.append("# Weekly Digest — latest")

    lines += [
        f"\n## Week {week}",
        "",
        f"- Inbox items: **{inbox_n}**",
        f"- Media story: `{media_file}`",
        "- Fan energy:",
    ]
    for k, v in fan.items():
        lines.append(f"  - {k}: {v:.3f}")
    lines.append("- Coach morale:")
    for k, v in mor.items():
        lines.append(f"  - {k}: {v:.3f}")

    text = "\n".join(lines) + "\n"
    if out.exists():
        out.write_text(out.read_text(encoding="utf-8") + text, encoding="utf-8")
    else:
        out.write_text(text, encoding="utf-8")
