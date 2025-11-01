import csv, os
def log_world_event(path, week, school_id, event_id, intensity, persist_weeks, effects_json):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', newline='') as f:
        w = csv.writer(f)
        w.writerow([week, school_id, event_id, intensity, persist_weeks, effects_json])
