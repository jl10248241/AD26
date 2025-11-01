# engine/src/config_mirror.py
from __future__ import annotations
from pathlib import Path
import shutil
import sys
import time

ENGINE = Path(__file__).resolve().parents[1]  # .../engine
CANON = ENGINE / "config"     # source of truth
LEGACY = ENGINE / "configs"   # legacy alias some tools use

# File name patterns to sync (covers both styles you've used)
PATTERNS = ["*.config", "*.config.json", "*_config.json"]

def _ensure_dirs():
    CANON.mkdir(parents=True, exist_ok=True)
    LEGACY.mkdir(parents=True, exist_ok=True)

def _newer(src: Path, dst: Path) -> bool:
    if not dst.exists():
        return True
    try:
        return src.stat().st_mtime > dst.stat().st_mtime + 1e-6
    except Exception:
        return True

def _iter_files(root: Path):
    for pat in PATTERNS:
        yield from root.glob(pat)

def _copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

def sync():
    _ensure_dirs()

    # 1) push newer files from CANON -> LEGACY
    for f in _iter_files(CANON):
        target = LEGACY / f.name
        if _newer(f, target):
            _copy(f, target)

    # 2) pull newer files from LEGACY -> CANON (in case a tool wrote there)
    for f in _iter_files(LEGACY):
        target = CANON / f.name
        if _newer(f, target):
            _copy(f, target)

if __name__ == "__main__":
    try:
        sync()
        print(f"[config_mirror] Synced between '{CANON.relative_to(ENGINE)}' and '{LEGACY.relative_to(ENGINE)}'.")
        sys.exit(0)
    except Exception as e:
        print("[config_mirror] ERROR:", e, file=sys.stderr)
        sys.exit(1)
