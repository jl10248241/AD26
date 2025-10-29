# sandbox/batch_run_parallel.py
# Parallel weekly sim that runs REG (via advance_week) safely on Windows.
import os, sys, json, random
from itertools import repeat
from multiprocessing import Pool, cpu_count
from pathlib import Path

# Ensure child processes can import /src even on Windows "spawn"
SRC_PATH = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC_PATH not in sys.path:
    sys.path.append(SRC_PATH)

from models import Coach  # picklable simple class

RNG = random.Random(424242)

def jitter_traits(traits, amt=5):
    return {k: max(0.0, min(100.0, v + RNG.uniform(-amt, amt))) for k, v in traits.items()}

def make_coach(proto, idx):
    c = Coach()
    c.id = f"{proto['id']}_{idx:03d}"
    c.traits = jitter_traits(proto['traits'])
    c.stress = RNG.uniform(0, 10)
    c.morale = RNG.uniform(0, 10)
    c.archetype = proto['archetype']
    c.anchor_strength = None
    c.polarity_tags = set()
    return c

def process_coach_batch(args):
    """Run one week's sim for one coach batch and append to that batch's temp logs."""
    batch, week, trait_log_tmp, world_log_tmp = args

    # Re-ensure imports inside child process
    if SRC_PATH not in sys.path:
        sys.path.append(SRC_PATH)
    from advance_week import advance_week  # REG runs inside this

    # Run weekly driver for this batch (writes to batch-specific temp files)
    advance_week(batch, week, trait_log_tmp, schools=None, world_log_path=world_log_tmp)
    return True

def merge_files(part_paths, final_path):
    """Concatenate temp batch files -> final file."""
    if not part_paths:
        return
    Path(final_path).parent.mkdir(parents=True, exist_ok=True)
    # remove old merged file if exists
    if os.path.exists(final_path):
        os.remove(final_path)
    with open(final_path, "ab") as out:
        for p in part_paths:
            if os.path.exists(p):
                with open(p, "rb") as f:
                    out.write(f.read())

def main_parallel(
    weeks=104,
    trait_log_final=os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'TRAIT_HISTORY_LOG.csv'),
    world_log_final=os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'WORLD_EVENTS_LOG.csv'),
):
    os.makedirs(os.path.dirname(trait_log_final), exist_ok=True)

    # Seed coaches (~200)
    with open(os.path.join(os.path.dirname(__file__), 'sample_coaches.json'),'r') as f:
        seed = json.load(f)['coaches']
    coaches = [make_coach(proto, i+1) for proto in seed for i in range(20)]

    # Split into N batches (cap to avoid excessive processes)
    N = min(cpu_count(), 8)
    batches = [coaches[i::N] for i in range(N)]

    # Prepare temp file paths per batch
    base_logs = os.path.join(os.path.dirname(__file__), '..', 'data', 'logs')
    trait_tmp = [os.path.join(base_logs, f'TRAIT_HISTORY_LOG.b{i}.csv') for i in range(N)]
    world_tmp = [os.path.join(base_logs, f'WORLD_EVENTS_LOG.b{i}.csv') for i in range(N)]
    # Clean previous temp files
    for p in trait_tmp + world_tmp:
        if os.path.exists(p):
            os.remove(p)

    # Create one pool and reuse it for all weeks
    with Pool(processes=N) as pool:
        for week in range(1, weeks + 1):
            tasks = list(zip(batches, repeat(week), trait_tmp, world_tmp))
            pool.map(process_coach_batch, tasks)

    # Merge temp batch logs into final logs
    merge_files(trait_tmp, trait_log_final)
    merge_files(world_tmp, world_log_final)

if __name__ == "__main__":
    main_parallel()
