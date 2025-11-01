# engine/src/ui_recruiting_influence_cli.py (append/replace main as needed)
if __package__ in (None, ""):
    import sys, pathlib
    sys.path.append(str(pathlib.Path(__file__).resolve().parent))
    sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
    __package__ = "engine.src"

import argparse, json
from .recruiting_influence import apply_media_reach_to_probability as apply_mr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

def cmd_report(_):
    DOCS.mkdir(parents=True, exist_ok=True)
    base = 0.30
    rows = []
    for z in ("Local","Regional","National"):
        out = apply_mr(base, z)
        rows.append((z, f"{base:.2f} → {out:.2f}"))
    md = ["# Recruiting — Media Influence (current)","","| Zone | 0.30 Base → Applied |","|---|---:|"]
    md += [f"| {z} | {val} |" for z,val in rows]
    (DOCS/"RECRUITING_READOUT.md").write_text("\n".join(md), encoding="utf-8")
    print("Wrote docs/RECRUITING_READOUT.md")

def cmd_prob(a):
    print(f"{a.zone}: {a.base:.3f} → {apply_mr(a.base,a.zone):.3f}")

def cmd_show(a):
    base = 0.30
    for z in ("Local","Regional","National"):
        print(f"{z}: {base:.2f} → {apply_mr(base, z):.2f}")
    if a.verbose: print("Verbose: media reach integration active.")

def cmd_compute(_):
    print("compute: pipeline hook OK")

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p.add_argument("--verbose", action="store_true")

    p_show = sub.add_parser("show");      p_show.set_defaults(func=cmd_show)
    p_prob = sub.add_parser("prob");      p_prob.add_argument("--base",type=float,required=True); p_prob.add_argument("--zone",choices=("Local","Regional","National"),required=True); p_prob.set_defaults(func=cmd_prob)
    p_rep  = sub.add_parser("report");    p_rep.set_defaults(func=cmd_report)
    p_cmp  = sub.add_parser("compute");   p_cmp.set_defaults(func=cmd_compute)

    a = p.parse_args(); a.func(a)

if __name__ == "__main__": main()
