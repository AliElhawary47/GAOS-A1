"""
GAOS™ MODULE 14 — Weekly Revenue Snapshot
Zone 3: Report | Standalone: £800 | In: GAOS™ Pro, Enterprise

Every Monday at 8am, reads the Invoice_Log sheet and emails the owner
a clean revenue summary — total invoiced, number of invoices, average
value, and a week-on-week comparison. No paid tools required.

Target client: Any invoicing business — agencies, accountants, trades.
Pain solved:   Not knowing weekly revenue without manually totalling spreadsheets.
"""

import re
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("revenue_snapshot")

REPORT_HOUR    = 8
REPORT_WEEKDAY = 0   # Monday = 0


def parse_amount(amount_str):
    """Extract numeric value from a string like '£1,234.56'."""
    try:
        cleaned = re.sub(r"[^\d.]", "", str(amount_str))
        return float(cleaned) if cleaned else 0.0
    except Exception:
        return 0.0


def week_range(weeks_ago=0):
    """Return (start_date, end_date) for a given week offset."""
    today      = datetime.now().date()
    week_start = today - timedelta(days=today.weekday() + (7 * (weeks_ago + 1)))
    week_end   = week_start + timedelta(days=6)
    return week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")


def get_week_totals(rows, week_start, week_end):
    """Sum invoices that fall within the date range."""
    total = 0.0
    count = 0
    for row in rows:
        # "Received" rows are supplier invoices logged by module 01 — not revenue
        if str(row.get("Status", "")).strip().lower() == "received":
            continue
        inv_dt = core.parse_date(row.get("Invoice Date", ""))
        if not inv_dt:
            continue
        invoiced = inv_dt.strftime("%Y-%m-%d")
        if week_start <= invoiced <= week_end:
            total += parse_amount(row.get("Amount", "0"))
            count += 1
    return total, count


def generate_snapshot(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("invoices", "Invoice_Log")
    rows     = core.sheets_read_all(sheet_id, tab)

    this_start, this_end   = week_range(0)
    last_start, last_end   = week_range(1)

    this_total, this_count = get_week_totals(rows, this_start, this_end)
    last_total, last_count = get_week_totals(rows, last_start, last_end)

    avg    = this_total / this_count if this_count else 0
    change = this_total - last_total
    arrow  = "▲" if change >= 0 else "▼"

    body = (
        f"Weekly Revenue Snapshot\n"
        f"{'─'*40}\n"
        f"Week: {this_start} to {this_end}\n\n"
        f"Total Invoiced:     £{this_total:,.2f}\n"
        f"Number of Invoices: {this_count}\n"
        f"Average Invoice:    £{avg:,.2f}\n\n"
        f"vs Last Week:       {arrow} £{abs(change):,.2f} "
        f"({'up' if change >= 0 else 'down'} from £{last_total:,.2f})\n\n"
        f"{'─'*40}\n"
        f"Aether Frameworks — GAOS™ Weekly Report"
    )

    core.gmail_send(
        gmail, cfg["gmail"]["alert_email"], cfg["gmail"]["watch_inbox"],
        f"GAOS Weekly Revenue — w/e {this_end}", body
    )
    log.info(f"Revenue snapshot sent. This week: £{this_total:,.2f} ({this_count} invoices)")


def _maybe_run(gmail, cfg):
    if core.should_run_at(REPORT_HOUR, weekday=REPORT_WEEKDAY):
        generate_snapshot(gmail, cfg)


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("module_14_revenue_snapshot: Scheduled every Monday at 8am.")
    core.run_loop(lambda: _maybe_run(gmail, cfg), 300)


if __name__ == "__main__":
    run()
