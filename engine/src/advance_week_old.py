import os
from loaders import load_cfg, load_gravity, load_archetype_anchors, load_contexts
from engine import advance_week_trait_engine
from logger import log_trait_history
from asserts import assert_ranges, assert_delta_limit
CFG = load_cfg(); G = load_gravity(); ANCH = load_archetype_anchors(); CTX = load_contexts()
def advance_week(coaches, week, log_path):
    if CFG['flags'].get('trait_engine_on','true').lower() != 'true':
        return
    for c in coaches:
        pre, post, delta, active = advance_week_trait_engine(c, CFG, G, ANCH, CTX, week)
        assert_ranges(post); assert_delta_limit(delta)
        log_trait_history(log_path, week, c.id, pre, post, delta, active, list(getattr(c, 'polarity_tags', set())))
