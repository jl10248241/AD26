# engine/src/schedule_executor.py
from __future__ import annotations
from pathlib import Path
import json
from .config_paths import STATE

STATE.mkdir(parents=True, exist_ok=True)

def _read_json(path: Path, default):
    try:
        if path.exists() and path.stat().st_size > 0:
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def execute_schedule(week: int):
    """
    Simple schedule processor:
    - load engine/state/schedule.json (list of entries)
    - select entries where entry.get('week') == week
    - mark them as executed and move to schedule_state.json (history)
    - return dict summary with executed events
    """
    sched_path = STATE / "schedule.json"
    history_path = STATE / "schedule_state.json"

    schedule = _read_json(sched_path, [])
    history = _read_json(history_path, [])

    to_run = [e for e in schedule if int(e.get("week", -1)) == int(week)]

    executed = []
    for e in to_run:
        # create a simple execution record
        rec = {
            "week": week,
            "timestamp": __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "id": e.get("id") or f"evt-{len(history)+len(executed)+1}",
            "type": e.get("type", "generic"),
            "title": e.get("title", ""),
            "actor": e.get("actor", ""),
            "target": e.get("target", ""),
            "notes": e.get("notes", ""),
        }
        executed.append(rec)
        history.append(rec)

    # Optionally remove executed entries from schedule (so they don't run twice)
    remaining = [e for e in schedule if int(e.get("week", -1)) != int(week)]

    _write_json(sched_path, remaining)
    _write_json(history_path, history)

    return {"executed_count": len(executed), "executed": executed}
