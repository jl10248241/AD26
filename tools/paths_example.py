from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = {}
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k,v = line.split("=",1); ENV[k.strip()] = v.strip()

LOG_DIR = (ROOT / ENV.get("LOG_DIR","logs")).resolve()
CONFIG_DIR = (ROOT / ENV.get("CONFIG_DIR","configs")).resolve()
DOCS_DIR = (ROOT / ENV.get("DOCS_DIR","docs")).resolve()
DATA_DIR = (ROOT / ENV.get("DATA_DIR","data")).resolve()

TRAIT_LOG = LOG_DIR / "TRAIT_HISTORY_LOG.csv"
WORLD_LOG  = LOG_DIR / "WORLD_EVENTS_LOG.csv"
FINANCE_LOG = LOG_DIR / "FINANCE_LOG.csv"

TRAIT_COMPONENTS = CONFIG_DIR / "trait_components.json"
REG_CATALOG = CONFIG_DIR / "reg_catalog.json"
REG_WEIGHTS = CONFIG_DIR / "reg_weights.json"
