# engine/src/recruiting_bonus.py
from __future__ import annotations
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "engine" / "state"
DOCS = ROOT / "docs"
FACTORS = STATE / "PRESTIGE_FACTORS.json"
OUT = DOCS / "RECRUITING_BONUS.md"

def main():
    if not FACTORS.exists():
        raise SystemExit("[recruiting_bonus] Run `python -m engine.src.prestige_factors` first.")
    data = json.loads(FACTORS.read_text(encoding="utf-8"))

    items = []
    for school, f in data.items():
        r = float(f.get("recruiting_mult", 1.0))
        bonus = round((r - 1.0) * 100.0, 1)   # e.g., 1.06 → +6.0%
        items.append((school, r, bonus))
    items.sort(key=lambda t: t[1], reverse=True)

    lines = [
        "# Recruiting Bonus — derived from AD Current Prestige",
        "",
        "| Rank | School | Recruiting× | Bonus |",
        "|---:|---|---:|---:|",
    ]
    for i, (school, mult, bonus) in enumerate(items, 1):
        sign = "+" if bonus >= 0 else ""
        lines.append(f"| {i} | {school} | {mult:.3f} | {sign}{bonus:.1f}% |")

    DOCS.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("OK:", OUT)

if __name__ == "__main__":
    main()
