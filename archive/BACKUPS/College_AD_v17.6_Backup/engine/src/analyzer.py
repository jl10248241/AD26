# src/analyzer.py — College AD v17.5 (Enhanced)
# Finance / Prestige / Sentiment Trends → writes docs/FINANCE_TRENDS.md
# Safe, dependency-free, and runnable even when logs are missing.

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass
import csv
import datetime
import logging
import statistics
from functools import lru_cache
from contextlib import contextmanager
import argparse

# --- Logging Configuration ----------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Configuration Constants --------------------------------------------------
class Config:
    """Centralized configuration constants"""
    DEFAULT_TREND_WINDOW = 4
    SPARKLINE_WIDTH = 20
    EPSILON = 1e-9
    MAX_SPARKLINE_WIDTH = 100
    EXPECTED_CSV_COLUMNS = {
        "week", "school", "donor_yield", "expenses", "balance", "prestige_change", "sentiment"
    }

# --- Data Models --------------------------------------------------------------
@dataclass
class FinanceRecord:
    """Structured finance record for type safety"""
    week: int
    school: str
    donor_yield: float
    expenses: float
    balance: float
    prestige_change: float
    sentiment: float

@dataclass
class SchoolSummary:
    """Summary statistics for a school"""
    weeks_count: int
    week_first: int
    week_last: int
    donor_total: float
    expenses_total: float
    balance_last: float
    prestige_cum: float
    sentiment_last: float
    balance_trend: float
    sentiment_trend: float
    spark_balance: str
    spark_donor: str
    spark_sent: str

# --- Workspace roots ----------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]

def load_env() -> Dict[str, str]:
    """Load environment variables from .env file"""
    env: Dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
        except Exception as e:
            logger.warning(f"Failed to load .env file: {e}")
    return env

ENV = load_env()
LOG_DIR = (ROOT / ENV.get("LOG_DIR", "logs")).resolve()
DOCS_DIR = (ROOT / ENV.get("DOCS_DIR", "docs")).resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)

FINANCE_LOG = LOG_DIR / "FINANCE_LOG.csv"
OUT_MD      = DOCS_DIR / "FINANCE_TRENDS.md"

# --- Utility Functions --------------------------------------------------------
def _to_float(x, default=0.0) -> float:
    """Convert to float with robust error handling and light cleaning."""
    if x is None or x == "":
        return float(default)
    try:
        return float(x)
    except (ValueError, TypeError):
        try:
            cleaned = str(x).replace(",", "").replace("$", "").strip()
            return float(cleaned)
        except (ValueError, TypeError):
            logger.debug(f"Failed to convert '{x}' to float, using default {default}")
            return float(default)

def _to_int(x, default=0) -> int:
    """Convert to int with robust error handling."""
    if x is None or x == "":
        return int(default)
    try:
        return int(float(x))
    except (ValueError, TypeError):
        logger.debug(f"Failed to convert '{x}' to int, using default {default}")
        return int(default)

def _fmt_money(v: float) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.0f}"

def _fmt_num(v: float, p: int = 2) -> str:
    return f"{v:.{p}f}"

def _arrow(delta: float, eps: float = None) -> str:
    eps = eps or Config.EPSILON
    if delta > eps:
        return "↑"
    if delta < -eps:
        return "↓"
    return "→"

@lru_cache(maxsize=256)
def _asciispark_cached(data_tuple: Tuple[float, ...], width: int = Config.SPARKLINE_WIDTH) -> str:
    return _asciispark(list(data_tuple), width)

def _asciispark(series: List[float], width: int = None) -> str:
    """ASCII sparkline using blocks ▁▂▃▄▅▆▇█"""
    if not series:
        return "·" * 10
    width = width or Config.SPARKLINE_WIDTH
    width = min(max(5, width), Config.MAX_SPARKLINE_WIDTH)
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(series), max(series)
    if abs(hi - lo) < Config.EPSILON:
        mid_block = blocks[len(blocks) // 2]
        return mid_block * min(width, len(series))
    if len(series) > width:
        # downsample
        step = len(series) / width
        idxs = [int(i * step) for i in range(width)]
        series = [series[i] for i in idxs]
    out = []
    span = hi - lo
    for v in series:
        t = (v - lo) / span
        idx = min(int(t * (len(blocks) - 1)), len(blocks) - 1)
        out.append(blocks[idx])
    return "".join(out)

# --- Context Managers ---------------------------------------------------------
@contextmanager
def safe_file_operation(path: Path, mode: str = 'r'):
    """Context manager for safe file operations"""
    fp = None
    try:
        fp = path.open(mode, encoding='utf-8')
        yield fp
    finally:
        if fp:
            fp.close()

# --- Data Loading -------------------------------------------------------------
def validate_csv_headers(headers: List[str]) -> bool:
    """Validate CSV has required columns; warn but allow if missing."""
    header_set = set(headers or [])
    missing = Config.EXPECTED_CSV_COLUMNS - header_set
    if missing:
        logger.warning(f"Finance log missing columns {missing}. Attempting best-effort parse.")
        return False
    return True

def _read_finance_log(path: Path) -> List[FinanceRecord]:
    """Read and parse finance log CSV with validation."""
    if not path.exists():
        logger.warning(f"Finance log not found: {path}")
        return []
    rows: List[FinanceRecord] = []
    try:
        with safe_file_operation(path, 'r') as fp:
            reader = csv.DictReader(fp)
            if reader.fieldnames:
                validate_csv_headers(reader.fieldnames)
            for idx, r in enumerate(reader, start=1):
                try:
                    rows.append(FinanceRecord(
                        week=_to_int(r.get("week")),
                        school=(r.get("school") or "UNKNOWN").strip(),
                        donor_yield=_to_float(r.get("donor_yield")),
                        expenses=_to_float(r.get("expenses")),
                        balance=_to_float(r.get("balance")),
                        prestige_change=_to_float(r.get("prestige_change")),
                        sentiment=_to_float(r.get("sentiment")),
                    ))
                except Exception as e:
                    logger.warning(f"Skipping malformed row {idx}: {e}")
    except Exception as e:
        logger.error(f"Failed to read finance log: {e}")
        return []
    rows.sort(key=lambda x: (x.week, x.school))
    logger.info(f"Loaded {len(rows)} finance records from {path}")
    return rows

# --- Aggregation --------------------------------------------------------------
def _group_by_school(rows: List[FinanceRecord]) -> Dict[str, List[FinanceRecord]]:
    by_school: Dict[str, List[FinanceRecord]] = defaultdict(list)
    for rec in rows:
        by_school[rec.school].append(rec)
    for k in by_school:
        by_school[k].sort(key=lambda r: r.week)
    return dict(sorted(by_school.items()))

def _trend_delta(series: List[float], window: int = None) -> float:
    """Trend as difference of two moving averages for stability."""
    if not series:
        return 0.0
    window = window or Config.DEFAULT_TREND_WINDOW
    w = max(1, min(window, len(series)))
    recent_avg = statistics.fmean(series[-w:])
    # If not enough history, compare against the value w steps back, else prior window
    if len(series) >= 2 * w:
        older_avg = statistics.fmean(series[-2*w:-w])
    elif len(series) > w:
        older_avg = series[-w-1]
    else:
        older_avg = series[0]
    return recent_avg - older_avg

def _summarize_school(rows: List[FinanceRecord]) -> SchoolSummary:
    if not rows:
        return SchoolSummary(
            weeks_count=0, week_first=0, week_last=0,
            donor_total=0.0, expenses_total=0.0, balance_last=0.0,
            prestige_cum=0.0, sentiment_last=0.0,
            balance_trend=0.0, sentiment_trend=0.0,
            spark_balance="", spark_donor="", spark_sent=""
        )
    weeks = [r.week for r in rows]
    donors = [r.donor_yield for r in rows]
    expenses = [r.expenses for r in rows]
    balances = [r.balance for r in rows]
    prestige_d = [r.prestige_change for r in rows]
    sentiments = [r.sentiment for r in rows]
    return SchoolSummary(
        weeks_count=len(rows),
        week_first=weeks[0],
        week_last=weeks[-1],
        donor_total=sum(donors),
        expenses_total=sum(expenses),
        balance_last=balances[-1],
        prestige_cum=sum(prestige_d),
        sentiment_last=sentiments[-1],
        balance_trend=_trend_delta(balances),
        sentiment_trend=_trend_delta(sentiments),
        spark_balance=_asciispark_cached(tuple(balances)),
        spark_donor=_asciispark_cached(tuple(donors)),
        spark_sent=_asciispark_cached(tuple(sentiments)),
    )

# --- Markdown Generation ------------------------------------------------------
def _md_header(title: str, level: int = 1) -> str:
    return f"{'#' * level} {title}\n\n"

def _md_table(headers: List[str], rows: List[List[str]]) -> str:
    if not headers:
        return ""
    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out) + "\n\n"

def _build_overview_section(by_school: Dict[str, List[FinanceRecord]],
                            total_donors: float,
                            total_expenses: float) -> str:
    md = []
    md.append(f"- **Schools:** {len(by_school)}\n")
    md.append(f"- **Total Donor Yield (all-time):** {_fmt_money(total_donors)}\n")
    md.append(f"- **Total Expenses (all-time):** {_fmt_money(total_expenses)}\n\n")
    return "".join(md)

def _build_balance_table(by_school: Dict[str, List[FinanceRecord]]) -> str:
    headers = ["School", "Latest Balance", "Donor (Σ)", "Expenses (Σ)",
               "Prestige (ΣΔ)", "Sentiment (last)"]
    table_rows = []
    for school, records in by_school.items():
        summ = _summarize_school(records)
        table_rows.append([
            school,
            _fmt_money(summ.balance_last),
            _fmt_money(summ.donor_total),
            _fmt_money(summ.expenses_total),
            _fmt_num(summ.prestige_cum, 3),
            _fmt_num(summ.sentiment_last, 3),
        ])
    return _md_table(headers, table_rows)

def _build_school_trend_section(school: str, summary: SchoolSummary) -> str:
    md = []
    md.append(_md_header(f"{school} — Weekly Trends", level=2))
    md.append(
        f"- **Weeks:** {summary.weeks_count} "
        f"(first: {summary.week_first}, last: {summary.week_last})\n"
    )
    md.append(
        f"- **Balance trend (last {Config.DEFAULT_TREND_WINDOW}w):** "
        f"{_fmt_money(summary.balance_trend)} {_arrow(summary.balance_trend)}\n"
    )
    md.append(
        f"- **Sentiment trend (last {Config.DEFAULT_TREND_WINDOW}w):** "
        f"{_fmt_num(summary.sentiment_trend, 3)} {_arrow(summary.sentiment_trend)}\n\n"
    )
    md.append("**Sparklines**  \n")
    md.append(f"- Balance: `{summary.spark_balance}`  \n")
    md.append(f"- Donor Yield: `{summary.spark_donor}`  \n")
    md.append(f"- Sentiment: `{summary.spark_sent}`  \n\n")
    return "".join(md)

def _build_report(rows: List[FinanceRecord]) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if not rows:
        md = []
        md.append(_md_header("Finance, Prestige & Sentiment Trends (v17.5)"))
        md.append(f"_Generated: {now}_\n\n")
        md.append("> No finance log data found. Run at least one simulation week to generate `logs/FINANCE_LOG.csv`.\n\n")
        md.append("**Expected CSV columns:** `week, school, donor_yield, expenses, balance, prestige_change, sentiment`\n")
        return "".join(md)
    by_school = _group_by_school(rows)
    total_donors = sum(r.donor_yield for r in rows)
    total_expenses = sum(r.expenses for r in rows)
    md = []
    md.append(_md_header("Finance, Prestige & Sentiment Trends (v17.5)"))
    md.append(f"_Generated: {now}_\n\n")
    md.append(_build_overview_section(by_school, total_donors, total_expenses))
    md.append(_build_balance_table(by_school))
    for school, records in by_school.items():
        summary = _summarize_school(records)
        md.append(_build_school_trend_section(school, summary))
    return "".join(md)

# --- Public API ---------------------------------------------------------------
def analyze_finance(finance_log: Optional[Path] = None,
                    out_md: Optional[Path] = None) -> Path:
    """
    Reads FINANCE_LOG.csv, computes top-level and per-school trends,
    writes docs/FINANCE_TRENDS.md. Returns output path.
    """
    src = finance_log or FINANCE_LOG
    dst = out_md or OUT_MD
    logger.info(f"Starting finance analysis from {src}")
    rows = _read_finance_log(src)
    md = _build_report(rows)
    dst.write_text(md, encoding="utf-8")
    logger.info(f"Successfully wrote report to {dst}")
    return dst

# --- CLI Entry ----------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Analyze College AD finances and generate trends report.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Set logging level")
    parser.add_argument("--output", type=Path, help="Custom output path for markdown report")
    parser.add_argument("--input", type=Path, help="Custom input path for finance log CSV")
    args = parser.parse_args(argv)
    logging.getLogger().setLevel(args.log_level)
    out_path = analyze_finance(finance_log=args.input, out_md=args.output)
    print(f"[analyzer] Wrote trends report → {out_path}")

if __name__ == "__main__":
    main()
