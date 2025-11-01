def assert_ranges(vec):
    for k,v in vec.items():
        assert 0.0 <= v <= 100.0, f"{k} out of range: {v}"

def assert_delta_limit(delta, limit=6.0):
    for k,v in delta.items():
        assert abs(v) <= limit, f"Weekly delta too high: {k}={v}"

def assert_school_budget(school):
    dy = school.get("donor_yield", 1.0)
    assert 0.0 <= dy <= 5.0, f"donor_yield out of bounds: {dy}"

def assert_context_limit(coach, limit=4):
    ac = getattr(coach, "active_contexts", [])
    assert len(ac) <= limit, f"Too many active contexts: {len(ac)}"
