import argparse, json, csv
from pathlib import Path
from datetime import datetime

HEADER = ["timestamp", "role", "subject", "urgency", "file"]

def sniff(pkt: dict, default_role: str) -> tuple[str, str, str]:
    role = str(pkt.get("role", default_role))
    subject = str(pkt.get("subject", "(no subject)"))
    urgency = str(pkt.get("urgency", "INFO"))
    return role, subject, urgency

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default="logs/INBOX")
    ap.add_argument("--rebuild", action="store_true",
                    help="Recreate index from scratch")
    args = ap.parse_args()

    inbox = Path(args.inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    idx = inbox / "index.csv"

    if args.rebuild and idx.exists():
        idx.unlink()

    exists = idx.exists()
    with idx.open("a", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=HEADER)
        if not exists:
            w.writeheader()

        for p in sorted(inbox.glob("*.json"), key=lambda x: x.stat().st_mtime):
            try:
                pkt = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pkt = {}
            role, subject, urgency = sniff(pkt, default_role=p.stem.split("_", 1)[0])
            ts = datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
            w.writerow({"timestamp": ts, "role": role, "subject": subject,
                        "urgency": urgency, "file": p.name})

if __name__ == "__main__":
    main()
