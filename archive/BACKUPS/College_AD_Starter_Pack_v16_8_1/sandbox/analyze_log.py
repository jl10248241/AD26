import csv, statistics as stats, collections as C, os, json

TRAITS = ["Leadership","Charisma","Discipline","Empathy","Arrogance","Authenticity","Communication"]

def summarize_components(tc_path):
    with open(tc_path, 'r') as f:
        tc = json.load(f)
    print("=== Core Principle Weights (alpha={} ) ===".format(tc.get('meta',{}).get('alpha',0.35)))
    for t in TRAITS:
        node = tc.get(t,{}).get('weights',{})
        if node:
            s = sum(node.values())
            parts = ', '.join([f"{k}:{v:.2f}" for k,v in node.items()])
            print(f"{t:14s} -> {parts}  (Σ={s:.2f})")

def analyze(path, tc_path):
    rows = []
    with open(path) as f:
        r = csv.reader(f)
        for week, coach_id, trait, pre, post, delta, contexts, tags in r:
            rows.append((int(week), coach_id, trait, float(pre), float(post), float(delta)))
    by_trait = {t: [] for t in TRAITS}
    deltas = {t: [] for t in TRAITS}
    by_week = C.defaultdict(list)
    for w, _, t, pre, post, d in rows:
        if t in by_trait:
            by_trait[t].append(post)
            deltas[t].append(d)
            by_week[w].append(abs(d))
    print("=== Trait Summary ===")
    for t in TRAITS:
        if not by_trait[t]: continue
        mean = stats.mean(by_trait[t]); sd = stats.pstdev(by_trait[t]); dmax = max(abs(x) for x in deltas[t])
        print(f"{t:14s} mean={mean:5.2f} σ={sd:4.2f} max|Δ|/wk={dmax:4.2f}")
    print("\n=== Stability Checks ===")
    weekly_max = [max(v) for v in by_week.values()]
    print(f"max|Δ| any trait/week: {max(weekly_max):.2f}")
    print("\n"); summarize_components(tc_path)

if __name__ == "__main__":
    default = os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'TRAIT_HISTORY_LOG.csv')
    tc_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'trait_components.json')
    analyze(default, tc_path)
