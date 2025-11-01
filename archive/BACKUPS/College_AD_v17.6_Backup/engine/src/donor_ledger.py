from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
LEDGER = LOGS / "DONOR_LEDGER.csv"

def append_donor_entry(week: int, school: str, donor_id: str, donor_name: str, amount: float,
                       earmark: str = "", status: str = "pledged", note: str = ""):
    """Appends a donor entry to the ledger CSV."""
    exists = LEDGER.exists()
    with LEDGER.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["week", "school", "donor_id", "donor_name", "amount", "earmark", "status", "note"])
        writer.writerow([week, school, donor_id, donor_name, amount, earmark, status, note])
