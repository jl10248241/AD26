from __future__ import annotations
import json, io
from pathlib import Path
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]  # .../College_AD_Unified_Workspace_...
DOCS = ROOT / "docs"
STATE = ROOT / "engine" / "state"
LOGS  = ROOT / "logs"

def _read_json(p: Path) -> Any:
    if not p.exists(): return None
    with io.open(p, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def _read_md_table(md_path: Path) -> List[Dict[str, str]]:
    if not md_path.exists(): return []
    rows = []
    lines = md_path.read_text(encoding="utf-8-sig").splitlines()
    # find first pipe-table after header
    table_lines = [ln for ln in lines if "|" in ln]
    if len(table_lines) < 3: return []
    headers = [h.strip() for h in table_lines[0].split("|") if h.strip()]
    for ln in table_lines[2:]:
        cols = [c.strip() for c in ln.split("|") if c.strip()]
        if len(cols) != len(headers): continue
        rows.append(dict(zip(headers, cols)))
    return rows

app = FastAPI(title="AD Render Bus", version="0.1")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/media/reach")
def media_reach():
    p = DOCS / "MEDIA_REACH.json"
    data = _read_json(p)
    if not data:
        # fallback: parse map md to infer scores if needed
        data = {"scores": {"Local":0.0,"Regional":0.0,"National":0.0},
                "radii": {"Local":0,"Regional":0,"National":0}}
    data["asciimap_md_path"] = str(DOCS / "MEDIA_REACH_MAP.md")
    return data

@app.get("/recruiting/modifiers")
def recruiting_modifiers():
    p = STATE / "recruiting_modifiers.json"
    data = _read_json(p)
    if not data:
        raise HTTPException(404, "recruiting_modifiers.json not found — run the compute CLI first")
    return data

@app.get("/media/feed")
def media_feed():
    md = DOCS / "MEDIA_FEED.md"
    rows = _read_md_table(md)
    # Normalize keys
    out = []
    for r in rows:
        out.append({
            "when": r.get("When"),
            "title": r.get("Title"),
            "status": r.get("Status"),
            "sentiment": float(r.get("Sentiment", "0").replace("+","")),
            "file": None
        })
    return out

@app.get("/schedule/today")
def schedule_today():
    p = STATE / "schedule.json"
    data = _read_json(p) or {}
    today = data.get("today","")
    day = data.get("days",{}).get(today, {})
    return {
        "date": today,
        "used_hours": day.get("used_hours", 0),
        "total_hours": day.get("total_hours", 8),
        "items": day.get("items", [])
    }

@app.get("/relationships/node")
def relationships_node(name: str):
    p = STATE / "relationships.json"
    st = _read_json(p)
    if not st: raise HTTPException(404, "relationships.json not found")
    node = st.get("nodes", {}).get(name)
    if not node: raise HTTPException(404, f"node not found: {name}")
    out = {"node": name, "type": node.get("type","unknown"), "out": [], "in": []}
    for k, e in (st.get("edges") or {}).items():
        if "→" in k:
            src, tgt = k.split("→", 1)
            if src == name:
                out["out"].append({"target": tgt, **{m:e[m] for m in ("trust","rapport","influence")}})
            if tgt == name:
                out["in"].append({"source": src, **{m:e[m] for m in ("trust","rapport","influence")}})
    return out
