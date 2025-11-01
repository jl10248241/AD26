from pathlib import Path
import re

roots = [
    (Path("docs"), {"_golden"}),
    (Path("engine/config"), set()),
]

ignore = re.compile(r"(?:\.bak(?:$|[^/\\]))|(?:~$)|(?:#[^/\\]*$)|(?:\.tmp$)|(?:\.swp$)|(?:\.swx$)", re.IGNORECASE)

files = []
for root, exclude_dirs in roots:
    if not root.exists():
        continue
    for p in root.rglob('*'):\n        if not p.is_file():\n            continue\n        if 'archive' in str(p.parent).replace('\\\\','/').lower():\n            continue\n        if p.parent.name == '_docs':
            continue
        if p.parent.name in exclude_dirs:
            continue
        if ignore.search(p.name):
            continue
        files.append(p)

by_base = {}
for p in files:
    k = p.stem.lower()
    by_base.setdefault(k, []).append(p)

dups = {k: v for k, v in by_base.items() if len(v) > 1}

if dups:
    print("VALIDATION FAILED")
    for k, arr in dups.items():
        print(f" - Duplicate base name (config/docs) found: {k}")
        for p in arr:
            print(f"   - {p}")
    raise SystemExit(1)

print("Duplicate-basename scan OK.")

