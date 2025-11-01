import csv, os
def log_trait_history(path, week, coach_id, pre, post, delta, contexts, tags):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', newline='') as f:
        w = csv.writer(f)
        ctx = '|'.join(map(str, contexts)) if contexts else ''
        tgs = '|'.join(map(str, tags)) if tags else ''
        for k in post.keys():
            w.writerow([week, coach_id, k, pre[k], post[k], delta[k], ctx, tgs])
