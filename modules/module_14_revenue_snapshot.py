"""
GAOS™ MODULE 14 — Weekly Revenue Snapshot
Zone 3: Report | Standalone: £800 | In: GAOS™ Pro, Enterprise

Every Monday at 8am, reads the Invoice_Log sheet and emails the owner
a clean revenue summary — total invoiced, number of invoices, average
value, and a week-on-week comparison. No paid tools required.

Target client: Any invoicing business — agencies, accountants, trades.
Pain solved:   Not knowing weekly revenue without manually totalling spreadsheets.
"""

import time
import re
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("revenue_snapshot")

REPORT_HOUR    = 8
REPORT_WEEKDAY = 0   # Monday = 0


def is_report_time():
    now = datetime.now()
    return now.weekday() == REPORT_WEEKDAY and now.hour == REPORT_HOUR and now.minute < 5


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
        logged = str(row.get("Logged At", ""))[:10]
        if week_start <= logged <= week_end:
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


def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 14 - Weekly Revenue Snapshot")
    print("="*60 + "\n")
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Scheduled: every Monday at 8am. Ctrl+C to stop.\n")

    while True:
        try:
            if is_report_time():
                generate_snapshot(gmail, cfg)
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Snapshot error: {ex}")
        time.sleep(300)


if __name__ == "__main__":
    run()
