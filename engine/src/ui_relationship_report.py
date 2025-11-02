# ui_relationship_report.py — v19 Relationship Report CLI
import argparse, json, os, sys
from pathlib import Path
from relationship_core import project_paths, load_state

def render_table(state, top=20):
  rows = []
  for s, targets in state.items():
    for t, link in targets.items():
      score = round((link.trust + link.loyalty + link.respect)/3, 2)
      rows.append((score, s, t, link.trust, link.loyalty, link.respect))
  rows.sort(reverse=True, key=lambda r: r[0])
  head = f"{'SCORE':>6}  {'SUBJECT':<18}  {'TARGET':<22}  {'TRUST':>6}  {'LOYAL':>6}  {'RESPECT':>7}"
  print(head)
  print("-"*len(head))
  for row in rows[:top]:
    score, s, t, tr, lo, re = row
    print(f"{score:6.2f}  {s:<18}  {t:<22}  {tr:6.2f}  {lo:6.2f}  {re:7.2f}")

def render_md(state, top=50):
  rows = []
  for s, targets in state.items():
    for t, link in targets.items():
      score = round((link.trust + link.loyalty + link.respect)/3, 2)
      rows.append((score, s, t, link.trust, link.loyalty, link.respect))
  rows.sort(reverse=True, key=lambda r: r[0])
  out = []
  out.append("# Relationship Report — v19\n")
  out.append("| Score | Subject | Target | Trust | Loyalty | Respect |")
  out.append("|:-----:|:--------|:-------|------:|--------:|--------:|")
  for row in rows[:top]:
    score, s, t, tr, lo, re = row
    out.append(f"| {score:.2f} | {s} | {t} | {tr:.2f} | {lo:.2f} | {re:.2f} |")
  return "\n".join(out)

def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--project-root", required=True)
  ap.add_argument("--top", type=int, default=20)
  ap.add_argument("--md", action="store_true", help="emit markdown to stdout")
  args = ap.parse_args()

  paths = project_paths(Path(args.project_root))
  state = load_state(paths["state"])
  if args.md:
    print(render_md(state, args.top))
  else:
    render_table(state, args.top)

if __name__ == "__main__":
  main()
