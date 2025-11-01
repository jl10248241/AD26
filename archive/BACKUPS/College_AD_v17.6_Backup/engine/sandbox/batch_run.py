# sandbox/batch_run.py — v17.2: subtraits initialized; REG-first driver
import json, random, os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from models import Coach
from advance_week import advance_week
from loaders import load_trait_components

RNG = random.Random(424242)
TC = load_trait_components()

def jitter(x, amt=3):
    return max(0.0, min(100.0, x + RNG.uniform(-amt, amt)))

def jitter_traits(traits, amt=5):
    return {k: max(0.0, min(100.0, v + RNG.uniform(-amt, amt))) for k, v in traits.items()}

def init_subtraits_from_top(traits):
    subtraits = {}
    for trait, v in traits.items():
        node = TC.get(trait)
        if not node: 
            continue
        weights = node.get('weights', {})
        bundle = {}
        for name, w in weights.items():
            bundle[name] = jitter(v, amt=4)
        subtraits[trait] = bundle
    return subtraits

def make_coach(proto, idx):
    c = Coach()
    c.id = f"{proto['id']}_{idx:03d}"
    c.traits = jitter_traits(proto['traits'])
    c.stress = RNG.uniform(0, 10)
    c.morale = RNG.uniform(0, 10)
    c.archetype = proto['archetype']
    c.anchor_strength = None
    c.polarity_tags = set()
    c.active_contexts = []
    c.subtraits = init_subtraits_from_top(c.traits)
    return c

def make_school(id, coach):
    return {"id": id, "coach": coach, "prestige": 60.0, "donor_yield": 1.0, "sentiment": 0.0}

def main(weeks=104,
         trait_log=os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'TRAIT_HISTORY_LOG.csv'),
         world_log=os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'WORLD_EVENTS_LOG.csv')):

    os.makedirs(os.path.dirname(trait_log), exist_ok=True)

    with open(os.path.join(os.path.dirname(__file__), 'sample_coaches.json'),'r') as f:
        seed = json.load(f)['coaches']

    coaches = []
    for proto in seed:
        for i in range(20):
            coaches.append(make_coach(proto, i+1))

    schools = [make_school(f"SCH_{c.id}", c) for c in coaches]

    for week in range(1, weeks+1):
        advance_week(coaches, week, trait_log, schools=schools, world_log_path=world_log)

if __name__ == "__main__":
    main()
