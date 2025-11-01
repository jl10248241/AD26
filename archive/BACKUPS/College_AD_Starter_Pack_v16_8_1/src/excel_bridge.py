# src/excel_bridge.py
from __future__ import annotations
import sys, os, time
from pathlib import Path

# Optional faster JSON (falls back to stdlib)
try:
    import orjson as _json
    def _loads(b: bytes): return _json.loads(b)
    def _dumps(o, *, pretty: bool): 
        opt = _json.OPT_INDENT_2 if pretty else 0
        return _json.dumps(o, option=opt)
except Exception:
    import json as _json
    def _loads(b: bytes): return _json.loads(b.decode("utf-8"))
    def _dumps(o, *, pretty: bool): 
        return (_json.dumps(o, indent=2) if pretty else _json.dumps(o)).encode("utf-8")

from run_tick import run_one_tick

# ------------ helpers ------------
def _read_bytes(p: Path) -> bytes:
    with p.open("rb") as f:
        return f.read()

def _write_atomic(p: Path, data: bytes) -> None:
    """Atomic-ish write to avoid partial files on Windows."""
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(p)

def _must_exist(p: Path, label: str):
    if not p.exists():
        raise FileNotFoundError(f"[excel_bridge] Missing {label}: {p}")

# ------------ static cache ------------
_STATIC_CACHE = None
_STATIC_MTIMES = None

def _load_static(root: Path):
    """
    Load config/gravity/anchors/contexts once.
    If files change on disk (mtime change), refresh automatically.
    """
    global _STATIC_CACHE, _STATIC_MTIMES
    in_dir = root / "bridge_in"
    cfg_p   = in_dir / "config.json"
    g_p     = in_dir / "gravity.json"
    anch_p  = in_dir / "anchors.json"
    ctx_p   = in_dir / "contexts.json"

    for p, label in [(cfg_p,"config.json"), (g_p,"gravity.json"),
                     (anch_p,"anchors.json"), (ctx_p,"contexts.json")]:
        _must_exist(p, label)

    mtimes = (cfg_p.stat().st_mtime, g_p.stat().st_mtime,
              anch_p.stat().st_mtime, ctx_p.stat().st_mtime)

    if _STATIC_CACHE is None or _STATIC_MTIMES != mtimes:
        cfg   = _loads(_read_bytes(cfg_p))
        G     = _loads(_read_bytes(g_p))
        ANCH  = _loads(_read_bytes(anch_p))
        CTX   = _loads(_read_bytes(ctx_p))
        _STATIC_CACHE = (cfg, G, ANCH, CTX)
        _STATIC_MTIMES = mtimes
    return _STATIC_CACHE

# ------------ main ------------
def main(project_root: Path, pretty_out: bool = True):
    root = Path(project_root)
    in_dir  = root / "bridge_in"
    out_dir = root / "bridge_out"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Load dynamic state
    coaches_p = in_dir / "coaches.json"
    world_p   = in_dir / "world.json"
    meta_p    = in_dir / "meta.json"
    for p, label in [(coaches_p,"coaches.json"),
                     (world_p,"world.json"),
                     (meta_p,"meta.json")]:
        _must_exist(p, label)

    coaches = _loads(_read_bytes(coaches_p))
    world   = _loads(_read_bytes(world_p))
    meta    = _loads(_read_bytes(meta_p))
    week    = int(meta.get("week", 0))

    # 2) Load static (cached across ticks; auto-refresh if file changed)
    cfg, G, ANCH, CTX = _load_static(root)

    # 3) Run one tick (REG -> DBS)
    log_csv = str(root / "WORLD_EVENTS_LOG.csv")
    logs = run_one_tick(coaches, world, cfg, G, ANCH, CTX, week, rng=None, log_csv_path=log_csv)

    # 4) Write results back (atomic; pretty in dev, compact in prod)
    _write_atomic(out_dir / "coaches.json", _dumps(coaches, pretty=pretty_out))
    _write_atomic(out_dir / "world.json",   _dumps(world,   pretty=pretty_out))
    _write_atomic(out_dir / "logs.json",    _dumps(logs,    pretty=pretty_out))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.excel_bridge <PROJECT_ROOT> [--compact]")
        sys.exit(2)
    project = Path(sys.argv[1])
    pretty = True
    if len(sys.argv) > 2 and sys.argv[2] == "--compact":
        pretty = False
    main(project, pretty_out=pretty)
