from __future__ import annotations
import argparse, sys, json
from pathlib import Path
from .relationship_engine import ( seed_from_config,
    load_state, save_state, ensure_node, get_edge, interact, decay_all,
    _load_config
)

DOCS = Path("docs")
DOCS.mkdir(exist_ok=True)
REPORT_MD = DOCS / "RELATIONSHIPS.md"

def _is_empty(st: dict) -> bool:
    return not st or ("nodes" not in st) or ("edges" not in st) or (len(st["nodes"]) == 0 and len(st["edges"]) == 0)

def seed_defaults(st: dict) -> None:
    """
    Minimal, non-opinionated seed so first run is useful but not “gamey”.
    """
    for n in ["AD:State U", "Donor:MegaCorp", "Media:Local Beat", "Coach:Head Coach"]:
        ensure_node(st, n)
    # Create baseline edges (neutral metrics come from get_edge defaults)
    get_edge(st, "AD:State U", "Donor:MegaCorp")
    get_edge(st, "AD:State U", "Media:Local Beat")
    get_edge(st, "AD:State U", "Coach:Head Coach")

def write_report(st: dict) -> Path:
    """
    Simple Markdown snapshot of current graph.
    """
    lines = []
    lines.append("# Relationships — latest\n")
    nodes = sorted(st.get("nodes", {}).keys())
    edges = st.get("edges", {})

    lines.append("\n## Nodes\n")
    if nodes:
        for n in nodes:
            lines.append(f"- {n} ({st['nodes'][n].get('type','?')})")
    else:
        lines.append("_none_")

    lines.append("\n## Top edges (by influence)\n")
    if edges:
        # sort by influence desc, then trust desc
        top = sorted(edges.items(), key=lambda kv: (kv[1].get("influence",0), kv[1].get("trust",0)), reverse=True)[:25]
        lines.append("| Edge | Trust | Rapport | Influence |")
        lines.append("|---|---:|---:|---:|")
        for k,e in top:
            lines.append(f"| {k} | {e.get('trust',0):.3f} | {e.get('rapport',0):.3f} | {e.get('influence',0):.3f} |")
    else:
        lines.append("_none_")

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_MD

# ---------------- CLI commands ----------------

def cmd_list(args):
    st = load_state()
    if args.autoseed and _is_empty(st):
        seed_from_config(st)
        save_state(st)
    nodes = sorted(st.get("nodes", {}).keys())
    print("Nodes:")
    for n in nodes:
        print(" -", n)
    print("\nEdges:")
    for k, e in st.get("edges", {}).items():
        print(f" - {k}: T={e.get('trust',0):.3f} R={e.get('rapport',0):.3f} I={e.get('influence',0):.3f}")

def cmd_detail(args):
    st = load_state()
    if args.autoseed and _is_empty(st):
        seed_from_config(st)
        save_state(st)
    who = args.node
    print(f"Node: {who}")
    node_type = st.get("nodes", {}).get(who, {}).get("type","(unknown)")
    print("Type:", node_type)
    print("\nOutgoing:")
    for k, e in st.get("edges", {}).items():
        if k.startswith(f"{who}→"):
            tgt = k.split("→",1)[1]
            print(f" - {tgt}: T={e.get('trust',0):.3f} R={e.get('rapport',0):.3f} I={e.get('influence',0):.3f}")
    print("\nIncoming:")
    for k, e in st.get("edges", {}).items():
        if k.endswith(f"→{who}"):
            src = k.split("→",1)[0]
            print(f" - {src}: T={e.get('trust',0):.3f} R={e.get('rapport',0):.3f} I={e.get('influence',0):.3f}")

def cmd_interact(args):
    st = load_state()
    if args.autoseed and _is_empty(st):
        seed_from_config(st)
    e, rb = interact(st, args.actor, args.target, args.intent)
    save_state(st)
    print("OK")
    print(f" {args.actor} → {args.target} :: T={e['trust']:.3f} R={e['rapport']:.3f} I={e['influence']:.3f}")

def cmd_tick(args):
    st = load_state()
    if args.autoseed and _is_empty(st):
        seed_from_config(st)
    weeks = float(args.weeks)
    rate  = _load_config().get("decay_per_week", 0.01)
    decay_all(st, weeks, rate)
    save_state(st)
    print(f"Decayed {weeks} week(s) at rate {rate}")

def cmd_reset(args):
    # Reset to a blank—but valid—graph
    save_state({"nodes": {}, "edges": {}})
    print("State reset to empty.")

def cmd_report(args):
    st = load_state()
    if args.autoseed and _is_empty(st):
        seed_from_config(st)
        save_state(st)
    path = write_report(st)
    print(f"Report OK → {path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--autoseed", action="store_true", help="If graph is empty, create a minimal default cast/edges.")

    sp = ap.add_subparsers(dest="cmd", required=True)

    p_list = sp.add_parser("list", help="List nodes and edges")
    p_list.set_defaults(func=cmd_list)

    p_det = sp.add_parser("detail", help="Show one node detail")
    p_det.add_argument("node", type=str)
    p_det.set_defaults(func=cmd_detail)

    p_ix = sp.add_parser("interact", help="Apply an intent from actor→target")
    p_ix.add_argument("--actor", required=True)
    p_ix.add_argument("--target", required=True)
    p_ix.add_argument("--intent", required=True)
    p_ix.set_defaults(func=cmd_interact)

    p_tick = sp.add_parser("tick", help="Decay relationships by N weeks")
    p_tick.add_argument("--weeks", type=float, default=1.0)
    p_tick.set_defaults(func=cmd_tick)

    p_reset = sp.add_parser("reset", help="Reset relationships state to empty")
    p_reset.set_defaults(func=cmd_reset)

    p_rep = sp.add_parser("report", help="Write docs/RELATIONSHIPS.md snapshot")
    p_rep.set_defaults(func=cmd_report)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

