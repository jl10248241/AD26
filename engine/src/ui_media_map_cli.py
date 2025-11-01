from __future__ import annotations
import argparse, json, pathlib
from .media_map import build, write_doc

DOCS_DIR = pathlib.Path("docs")

def write_json(scores, radii):
    DOCS_DIR.mkdir(exist_ok=True)
    out = DOCS_DIR / "MEDIA_REACH.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"scores": scores, "radii": radii}, f, ensure_ascii=False, indent=2)

def cmd_render(_args=None):
    scores, radii, grid = build()
    write_doc(scores, radii, grid)
    write_json(scores, radii)
    print(json.dumps({"scores": scores, "radii": radii}, ensure_ascii=False, indent=2))

def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd")
    p = sp.add_parser("render", help="Render heatmap and export MEDIA_REACH.json")
    p.set_defaults(func=lambda a: cmd_render(a))
    args = ap.parse_args()
    if not getattr(args, "func", None):
        cmd_render(None)
    else:
        args.func(args)

if __name__ == "__main__":
    main()
