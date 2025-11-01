import json, configparser, os
from typing import Dict, Any
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
def load_cfg() -> Dict[str, Any]:
    cfg_path = os.path.join(CONFIG_DIR, "trait_engine.cfg")
    parser = configparser.ConfigParser()
    parser.read(cfg_path)
    return {s: dict(parser.items(s)) for s in parser.sections()}
def load_gravity() -> Dict[str, Dict[str, float]]:
    with open(os.path.join(CONFIG_DIR, "trait_gravity.json")) as f:
        return json.load(f)["matrix"]
def load_archetype_anchors() -> Dict[str, Dict[str, float]]:
    with open(os.path.join(CONFIG_DIR, "archetype_anchors.json")) as f:
        return json.load(f)["archetypes"]
def load_contexts() -> Dict[str, Any]:
    with open(os.path.join(CONFIG_DIR, "context_gravity.json")) as f:
        return json.load(f)
def load_trait_components() -> Dict[str, Any]:
    with open(os.path.join(CONFIG_DIR, "trait_components.json")) as f:
        tc = json.load(f)
    for trait, node in tc.items():
        if trait == "meta": continue
        w = node.get("weights", {})
        s = sum(w.values())
        if abs(s - 1.0) > 1e-6:
            raise ValueError(f"Subtrait weights for {trait} must sum to 1.0 (got {s})")
    return tc
