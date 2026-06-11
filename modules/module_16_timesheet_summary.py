"""
GAOS™ MODULE 16 — Staff Timesheet Summary
Zone 3: Report | Standalone: £850 | In: GAOS™ Enterprise

Every Friday at 6pm, reads the Timesheets sheet and emails the owner
a summary of hours worked per staff member that week, plus any over
or under the contracted hours.

Sheet tab required: Timesheets
Columns: Week Ending | Employee | Mon | Tue | Wed | Thu | Fri | Sat | Total Hours | Notes

Target client: Trades companies, agencies, any business with hourly/daily staff.
Pain solved:   Manually totalling timesheets before payroll or billing.
"""

from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("timesheet_summary")

REPORT_HOUR    = 18
REPORT_WEEKDAY = 4   # Friday


def generate_timesheet_summary(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("timesheets", "Timesheets")
    rows     = core.sheets_read_all(sheet_id, tab)

    if not rows:
        log.info("No timesheet data found.")
        return

    # Find the most recent week in the sheet (one row per employee per week)
    latest_week = max(
        (d for d in (core.parse_date(r.get("Week Ending", "")) for r in rows) if d),
        default=None,
    )
    if not latest_week:
        log.info("No parseable Week Ending dates found.")
        return
    week_ending = latest_week.strftime("%Y-%m-%d")

    # Sum hours per employee for the most recent week
    staff_hours = {}
    for row in rows:
        week_dt = core.parse_date(row.get("Week Ending", ""))
        name    = str(row.get("Employee", "")).strip()
        try:
            hours = float(str(row.get("Total Hours", "0")).replace(",", "").strip() or 0)
        except ValueError:
            hours = 0.0

        if week_dt and week_dt == latest_week and name:
            staff_hours[name] = staff_hours.get(name, 0.0) + hours

    if not staff_hours:
        log.info("No hours logged this week.")
        return

    total_hours = sum(staff_hours.values())
    lines = [f"  {name:<20} {hrs:.1f} hrs" for name, hrs in sorted(staff_hours.items())]

    body = (
        f"Staff Timesheet Summary\n"
        f"Week ending: {week_ending}\n"
        f"{'─'*40}\n\n"
        + "\n".join(lines) +
        f"\n\n{'─'*40}\n"
        f"Total hours this week: {total_hours:.1f}\n\n"
        f"Aether Frameworks — GAOS™ Timesheet Report"
    )

    core.gmail_send(
        gmail, cfg["gmail"]["alert_email"], cfg["gmail"]["watch_inbox"],
        f"GAOS Timesheet Summary — w/e {week_ending}", body
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
