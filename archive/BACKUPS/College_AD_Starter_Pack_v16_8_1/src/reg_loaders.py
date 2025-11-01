import json, os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")

def load_reg_catalog():
    with open(os.path.join(CONFIG_DIR, "reg_catalog.json")) as f:
        return json.load(f)

def load_reg_weights():
    with open(os.path.join(CONFIG_DIR, "reg_weights.json")) as f:
        return json.load(f)
