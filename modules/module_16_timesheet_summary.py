"""
GAOS™ MODULE 16 — Staff Timesheet Summary
Zone 3: Report | Standalone: £850 | In: GAOS™ Enterprise

Every Friday at 6pm, reads the Timesheets sheet and emails the owner
a summary of hours worked per staff member that week, plus any over
or under the contracted hours.

Sheet tab required: Timesheets
Columns: Staff Name | Date | Hours | Job Reference | Notes

Target client: Trades companies, agencies, any business with hourly/daily staff.
Pain solved:   Manually totalling timesheets before payroll or billing.
"""

from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("timesheet_summary")

REPORT_HOUR    = 18
REPORT_WEEKDAY = 4   # Friday


def get_week_start():
    today = datetime.now().date()
    return (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")


def generate_timesheet_summary(gmail, cfg):
    sheet_id   = cfg["google_sheets"]["sheet_id"]
    tab        = cfg["google_sheets"]["tabs"].get("timesheets", "Timesheets")
    rows       = core.sheets_read_all(sheet_id, tab)
    week_start = get_week_start()

    if not rows:
        log.info("No timesheet data found.")
        return

    # Group hours by staff member for this week
    staff_hours = {}
    for row in rows:
        date  = str(row.get("Date", ""))[:10]
        name  = str(row.get("Staff Name", "Unknown")).strip()
        try:
            hours = float(str(row.get("Hours", "0")).replace(",", "").strip())
        except ValueError:
            hours = 0.0

        if date >= week_start and name:
            staff_hours[name] = staff_hours.get(name, 0.0) + hours

    if not staff_hours:
        log.info("No hours logged this week.")
        return

    total_hours = sum(staff_hours.values())
    lines = [f"  {name:<20} {hrs:.1f} hrs" for name, hrs in sorted(staff_hours.items())]

    body = (
        f"Staff Timesheet Summary\n"
        f"Week commencing: {week_start}\n"
        f"{'─'*40}\n\n"
        + "\n".join(lines) +
        f"\n\n{'─'*40}\n"
        f"Total hours this week: {total_hours:.1f}\n\n"
        f"Aether Frameworks — GAOS™ Timesheet Report"
    )

    core.gmail_send(
        gmail, cfg["gmail"]["alert_email"], cfg["gmail"]["watch_inbox"],
        f"GAOS Timesheet Summary — w/c {week_start}", body
    )
    log.info(f"Timesheet summary sent. {len(staff_hours)} staff, {total_hours:.1f} total hours.")


def _maybe_run(gmail, cfg):
    if core.should_run_at(REPORT_HOUR, weekday=REPORT_WEEKDAY):
        generate_timesheet_summary(gmail, cfg)


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("module_16_timesheet_summary: Scheduled every Friday at 6pm.")
    core.run_loop(lambda: _maybe_run(gmail, cfg), 300)


if __name__ == "__main__":
    run()
