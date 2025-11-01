# engine/src/ad_seed.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import json

ROOT = Path(__file__).resolve().parents[2]
CONF_DIR = ROOT / "configs"

PROG_CONF = CONF_DIR / "ad_programs.config.json"
HEALTH_CONF = CONF_DIR / "ad_health.config.json"

def _load_json(p: Path, default: dict) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

_DEF_PROG = {
    "version":"1",
    "program_weights":{"fb":0.55,"mbb":0.2,"wbb":0.05,"base":0.05,"soft":0.03,"vb":0.02,"msoc":0.03,"wsoc":0.03,"track":0.04},
    "program_defaults":{"prestige":0.5,"history_index":0.3,"nostalgia":0.1},
    "facility_map":{
        "fb":{"name":"Main Stadium","type":"stadium"},
        "mbb":{"name":"Basketball Arena","type":"arena"},
        "wbb":{"name":"Basketball Arena","type":"arena"},
        "base":{"name":"Baseball Field","type":"field"},
        "soft":{"name":"Softball Field","type":"field"},
        "vb":{"name":"Volleyball Arena","type":"arena"},
        "msoc":{"name":"Soccer Field","type":"field"},
        "wsoc":{"name":"Soccer Field","type":"field"},
        "track":{"name":"Track Complex","type":"field"}
    },
    "facility_defaults":{"condition":0.75,"age_years":20,"nostalgia":0.2},
    "utility_facilities":[
        {"name":"Weight Room","type":"weight_room","program":"fb"},
        {"name":"Training Room","type":"training","program":"fb"}
    ]
}

def ensure_ad_scaffold(world: Dict[str, Any]) -> None:
    """
    Idempotently ensures per-school programs + facilities exist.
    Won't overwrite explicit values already present in a school.
    """
    cfg = _load_json(PROG_CONF, _DEF_PROG)
    prog_weights = cfg.get("program_weights", {})
    prog_def = cfg.get("program_defaults", {})
    fac_map = cfg.get("facility_map", {})
    fac_def = cfg.get("facility_defaults", {})
    utils = cfg.get("utility_facilities", [])

    for sch in world.get("schools", []):
        # Programs
        programs = sch.setdefault("programs", {})
        for prog_key in prog_weights.keys():
            p = programs.setdefault(prog_key, {})
            p.setdefault("prestige", float(prog_def.get("prestige", 0.5)))
            p.setdefault("history_index", float(prog_def.get("history_index", 0.3)))
            p.setdefault("nostalgia", float(p.get("nostalgia", prog_def.get("nostalgia", 0.1))))

        # Facilities
        facs: List[Dict[str, Any]] = sch.setdefault("facilities", [])
        # index existing by (type, program)
        have = {(f.get("type"), f.get("program")) for f in facs}
        # per-program primary
        for prog_key, spec in fac_map.items():
            t = spec.get("type"); nm = spec.get("name")
            key = (t, prog_key)
            if key not in have:
                facs.append({
                    "name": nm,
                    "type": t,
                    "program": prog_key,
                    "condition": float(fac_def.get("condition", 0.75)),
                    "age_years": float(fac_def.get("age_years", 20)),
                    "nostalgia": float(fac_def.get("nostalgia", 0.2))
                })
                have.add(key)
        # utilities
        for u in utils:
            key = (u.get("type"), u.get("program"))
            if key not in have:
                facs.append({
                    "name": u.get("name"),
                    "type": u.get("type"),
                    "program": u.get("program"),
                    "condition": float(fac_def.get("condition", 0.75)),
                    "age_years": float(fac_def.get("age_years", 15)),
                    "nostalgia": 0.0  # utilities default to zero nostalgia
                })
                have.add(key)

        # Top-level health scaffolds (neutral if missing)
        sch.setdefault("coach_morale", 0.5)
        sch.setdefault("board_support", 0.5)
        sch.setdefault("ad_health", {"score": 0.5})

if __name__ == "__main__":
    # demo seed for a tiny world
    demo = {"schools":[{"name":"State U"}, {"name":"School 029"}]}
    ensure_ad_scaffold(demo)
    print("Seeded:", list(demo["schools"][0].keys()))
