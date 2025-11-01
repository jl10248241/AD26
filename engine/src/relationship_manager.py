from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, math, random, datetime as dt
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine"
CONFIG = ENGINE / "config"
STATE  = ENGINE / "state"
STATE.mkdir(parents=True, exist_ok=True)

CFG_DOMAINS = CONFIG / "relationship_domains.config.json"
CFG_INTENTS = CONFIG / "relationship_intents.config.json"
CFG_PERSONA = CONFIG / "personas.config.json"
STATE_FILE  = STATE / "relationships.json"

RNG = random.Random(42)

def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _read_json(p: Path, fallback):
    try:
        if not p.exists() or p.stat().st_size == 0:
            return fallback
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def _write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def load_domains():
    cfg = _read_json(CFG_DOMAINS, {})
    return {
        "weights": cfg.get("weights", {"media":1.0,"coach":1.0,"donor":1.0,"board":0.8,"rival_ad":0.7}),
        "decay": cfg.get("decay", {"media":0.005,"coach":0.003,"donor":0.002,"board":0.002,"rival_ad":0.004}),
        "noise_std": cfg.get("noise_std", 0.01),
        "compat_gain": cfg.get("compat_gain", 0.5),
        "clamp": cfg.get("clamp", [0.0, 1.0])
    }

def load_intents():
    return _read_json(CFG_INTENTS, {
        "amplify_story":{"domain":"media","d_strength":+0.06,"d_trust":+0.04,"cooldown":1},
        "downplay_story":{"domain":"media","d_strength":-0.03,"d_trust":+0.01,"cooldown":1},
        "ask_donation":{"domain":"donor","d_strength":+0.04,"d_trust":+0.03,"cooldown":2},
        "thank_donor":{"domain":"donor","d_strength":+0.03,"d_trust":+0.05,"cooldown":1},
        "back_channel":{"domain":"rival_ad","d_strength":+0.03,"d_trust":+0.02,"cooldown":1},
        "hire_assistant":{"domain":"coach","d_strength":+0.05,"d_trust":+0.02,"cooldown":2},
        "support_board":{"domain":"board","d_strength":+0.02,"d_trust":+0.04,"cooldown":1},
    })

def load_personas():
    return _read_json(CFG_PERSONA, {
        "archetypes":{
            "AD_modern":{"E":0.65,"A":0.55,"C":0.70,"O":0.60,"S":0.60},
            "Coach_oldschool":{"E":0.55,"A":0.40,"C":0.75,"O":0.35,"S":0.55},
            "Coach_players":{"E":0.70,"A":0.70,"C":0.55,"O":0.60,"S":0.50},
            "Donor_corporate":{"E":0.50,"A":0.45,"C":0.80,"O":0.40,"S":0.70},
            "Media_local":{"E":0.60,"A":0.55,"C":0.50,"O":0.65,"S":0.55},
            "RivalAD_political":{"E":0.55,"A":0.35,"C":0.70,"O":0.45,"S":0.60},
            "Board_trustee":{"E":0.40,"A":0.50,"C":0.75,"O":0.35,"S":0.65}
        },
        "entities":{
            "AD:State U":{"type":"ad","archetype":"AD_modern"},
            "Coach:Head Coach":{"type":"coach","archetype":"Coach_oldschool"},
            "Donor:MegaCorp":{"type":"donor","archetype":"Donor_corporate"},
            "Media:Local Beat":{"type":"media","archetype":"Media_local"},
            "AD:State Rival":{"type":"rival_ad","archetype":"RivalAD_political"},
            "Board:Chair":{"type":"board","archetype":"Board_trustee"}
        },
        "seed_edges":[
            ["AD:State U","Coach:Head Coach",0.45,0.50],
            ["AD:State U","Donor:MegaCorp",0.40,0.45],
            ["AD:State U","Media:Local Beat",0.35,0.40],
            ["AD:State U","AD:State Rival",0.20,0.30],
            ["AD:State U","Board:Chair",0.30,0.35]
        ]
    })

@dataclass
class Edge:
    strength: float = 0.3
    trust: float = 0.3
    cooldown: int = 0

@dataclass
class Node:
    name: str
    typ: str
    traits: Dict[str, float]
    edges: Dict[str, Edge]

def _compat(a: Dict[str,float], b: Dict[str,float]) -> float:
    keys = ["E","A","C","O","S"]
    va = [a[k] for k in keys]; vb = [b[k] for k in keys]
    dot = sum(x*y for x,y in zip(va,vb))
    na = math.sqrt(sum(x*x for x in va)); nb = math.sqrt(sum(y*y for y in vb))
    if na == 0 or nb == 0: return 0.5
    cs = max(0.0, min(1.0, (dot/(na*nb))))
    return cs

def default_state():
    pers = load_personas()
    entities = {}
    for key, meta in pers["entities"].items():
        arch = pers["archetypes"][meta["archetype"]]
        entities[key] = asdict(Node(name=key, typ=meta["type"], traits=arch, edges={}))
    for src, dst, s, t in pers["seed_edges"]:
        _ensure_edge(entities, src, dst, s, t)
        _ensure_edge(entities, dst, src, s, t)
    return {"entities": entities, "updated": _now_iso()}

def _ensure_edge(entities, src, dst, s=0.3, t=0.3):
    a = entities[src]["edges"].get(dst)
    if a is None:
        entities[src]["edges"][dst] = asdict(Edge(strength=s, trust=t, cooldown=0))

def load_state():
    if not STATE_FILE.exists():
        st = default_state()
        _write_json(STATE_FILE, st)
        return st
    return _read_json(STATE_FILE, default_state())

def save_state(st):
    st["updated"] = _now_iso()
    _write_json(STATE_FILE, st)

def _clamp(x: float, bounds: List[float]) -> float:
    lo, hi = bounds
    return max(lo, min(hi, x))

def interact(actor: str, target: str, intent: str) -> Tuple[bool,str]:
    st = load_state()
    ents = st["entities"]
    if actor not in ents or target not in ents:
        return False, "Unknown actor/target."
    cfg_d = load_domains(); cfg_i = load_intents()
    if intent not in cfg_i: return False, f"Unknown intent '{intent}'."

    dom = cfg_i[intent]["domain"]
    w   = cfg_d["weights"].get(dom, 1.0)
    ds  = cfg_i[intent]["d_strength"] * w
    dt_ = cfg_i[intent]["d_trust"]    * w
    cd  = cfg_i[intent].get("cooldown", 1)

    _ensure_edge(ents, actor, target)
    _ensure_edge(ents, target, actor)
    e_fwd = Edge(**ents[actor]["edges"][target])
    e_rev = Edge(**ents[target]["edges"][actor])

    comp = _compat(ents[actor]["traits"], ents[target]["traits"])
    gain = 1.0 + load_domains()["compat_gain"]*(comp - 0.5)

    noise = random.gauss(0, load_domains()["noise_std"])
    e_fwd.strength = _clamp(e_fwd.strength + (ds*gain) + noise, load_domains()["clamp"])
    e_fwd.trust    = _clamp(e_fwd.trust    + (dt_*gain) + noise, load_domains()["clamp"])
    e_fwd.cooldown = max(e_fwd.cooldown, cd)

    spill = 0.35
    e_rev.strength = _clamp(e_rev.strength + (ds*gain*spill) + noise, load_domains()["clamp"])
    e_rev.trust    = _clamp(e_rev.trust    + (dt_*gain*spill) + noise, load_domains()["clamp"])

    ents[actor]["edges"][target] = asdict(e_fwd)
    ents[target]["edges"][actor] = asdict(e_rev)
    save_state(st)
    return True, f"OK: {actor} → {target} :: {intent} (comp={comp:.2f}, gain={gain:.2f})"

def tick(decay_scale: float = 1.0) -> Tuple[int,int]:
    st = load_state()
    ents = st["entities"]
    cfg_d = load_domains()
    dec = cfg_d["decay"]; std = cfg_d["noise_std"]
    updated_edges = 0; cooled = 0

    for src_name, src in ents.items():
        for dst_name, ed in list(src["edges"].items()):
            typ = ents[dst_name]["typ"]
            decay = dec.get(typ if typ in dec else "media", 0.003) * decay_scale
            base = 0.30
            e = Edge(**ed)
            e.strength += (base - e.strength) * decay + random.gauss(0, std*0.25)
            e.trust    += (base - e.trust)    * decay + random.gauss(0, std*0.25)
            e.strength = _clamp(e.strength, cfg_d["clamp"])
            e.trust    = _clamp(e.trust, cfg_d["clamp"])
            if e.cooldown > 0:
                e.cooldown -= 1
                cooled += 1
            src["edges"][dst_name] = asdict(e)
            updated_edges += 1

    save_state(st)
    return updated_edges, cooled

def get_summary(top_n: int = 20):
    st = load_state()
    ents = st["entities"]
    rows = []
    for src, data in ents.items():
        for dst, e in data["edges"].items():
            rows.append((src, dst, e["strength"], e["trust"]))
    rows.sort(key=lambda r: (r[2]+r[3]), reverse=True)
    return rows[:top_n]

def get_node(name: str):
    st = load_state()
    return st["entities"].get(name)

def list_nodes():
    st = load_state()
    return sorted(st["entities"].keys())
