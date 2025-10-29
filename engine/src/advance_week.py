# Drop-in replacement for advance_week.py that runs REG before Trait Engine
import os
from loaders import load_cfg, load_gravity, load_archetype_anchors, load_contexts
from reg_loaders import load_reg_catalog, load_reg_weights
from reg_engine import AdvanceWeek_REG
from engine import advance_week_trait_engine
from logger import log_trait_history
from asserts import assert_ranges, assert_delta_limit, assert_school_budget, assert_context_limit

CFG = load_cfg(); G = load_gravity(); ANCH = load_archetype_anchors(); CTX = load_contexts()
REG_CATALOG = load_reg_catalog(); REG_WEIGHTS = load_reg_weights()

def advance_week(coaches, week, log_path, schools=None, world_log_path=None):
    if CFG['flags'].get('trait_engine_on','true').lower() != 'true':
        return
    if schools is None:
        schools = [{"id": f"SCH_{c.id}", "coach": c, "prestige": 60.0, "donor_yield": 1.0, "sentiment": 0.0} for c in coaches]
    if world_log_path is None:
        world_log_path = os.path.join(os.path.dirname(log_path), "WORLD_EVENTS_LOG.csv")
    AdvanceWeek_REG(week, schools, REG_CATALOG, REG_WEIGHTS['Normal'], world_log_path)
    for s in schools:
        assert_school_budget(s)
    for c in coaches:
        if not hasattr(c, "active_contexts"):
            c.active_contexts = []
        pre, post, delta, active = advance_week_trait_engine(c, CFG, G, ANCH, CTX, week)
        assert_ranges(post); assert_delta_limit(delta); assert_context_limit(c)
        log_trait_history(log_path, week, c.id, pre, post, delta, active, list(getattr(c, 'polarity_tags', set())))
