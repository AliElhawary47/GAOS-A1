"""
GAOS™ MODULE 17 — Birthday & Anniversary Mailer
Zone 4: Schedule | Standalone: £650 | In: GAOS™ Enterprise

Every morning checks the Clients sheet for birthdays and contract
anniversaries. When a match is found it sends a personalised email
to the client and logs it so it never sends twice.

Sheet tab required: Clients
Columns: Name | Email | Phone | Type | Status | Last Contact | Birthday | Anniversary | Last Birthday Mail | Last Anniversary Mail | Re-Engaged | Notes

Target client: Gyms, clinics, consultants, estate agents, any relationship business.
Pain solved:   Missing the simple human touches that make clients stay loyal.
"""

from datetime import datetime
import gaos_core as core

log = core.get_logger("birthday_mailer")

SEND_HOUR = 9


def matches_today(date_str):
    """Returns True if month and day match today regardless of year."""
    dt = core.parse_date(date_str)
    if not dt:
        return False
    today = datetime.now()
    return dt.month == today.month and dt.day == today.day


def build_birthday_email(client_name, business_name):
    return (
        f"Dear {client_name},\n\n"
        f"Wishing you a very happy birthday from all of us here at {business_name}!\n\n"
        f"We hope you have a wonderful day.\n\n"
        f"With warm regards,\n{business_name}"
    )


def build_anniversary_email(client_name, business_name):
    today = datetime.now()
    return (
        f"Dear {client_name},\n\n"
        f"It's been a year since we started working together and we just wanted "
        f"to say thank you for being a valued client of {business_name}.\n\n"
        f"We look forward to continuing to support you.\n\n"
        f"With warm regards,\n{business_name}"
    )


def run_daily_check(gmail, cfg):
    sheet_id  = cfg["google_sheets"]["sheet_id"]
    tab       = cfg["google_sheets"]["tabs"].get("clients", "Clients")
    rows      = core.sheets_read_all(sheet_id, tab)
    this_year = str(datetime.now().year)
    sent      = 0

    for i, row in enumerate(rows):
        name   = str(row.get("Name",  "")).strip()
        email  = str(row.get("Email", "")).strip()
        bday   = str(row.get("Birthday", "")).strip()
        anniv  = str(row.get("Anniversary", "")).strip()
        last_b = str(row.get("Last Birthday Mail", "")).strip()
        last_a = str(row.get("Last Anniversary Mail", "")).strip()

        if not email or not name:
            continue

        # Birthday
        if bday and matches_today(bday) and last_b[:4] != this_year:
            body = build_birthday_email(name, cfg["business"]["name"])
            if core.gmail_send(gmail, email, cfg["gmail"]["watch_inbox"],
                               f"Happy Birthday from {cfg['business']['name']} 🎂", body):
                core.sheets_update_cell(sheet_id, tab, i + 2, "Last Birthday Mail", this_year)
                log.info(f"Birthday email sent to {name}")
                sent += 1

        # Anniversary
        if anniv and matches_today(anniv) and last_a[:4] != this_year:
            body = build_anniversary_email(name, cfg["business"]["name"])
            if core.gmail_send(gmail, email, cfg["gmail"]["watch_inbox"],
                               f"Thank you for a great year — {cfg['business']['name']}", body):
                core.sheets_update_cell(sheet_id, tab, i + 2, "Last Anniversary Mail", this_year)
                log.info(f"Anniversary email sent to {name}")
                sent += 1

    return sent


def _maybe_run(gmail, cfg):
    if core.should_run_at(SEND_HOUR):
        run_daily_check(gmail, cfg)


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info(f"module_17_birthday_mailer: Scheduled daily at {SEND_HOUR}:00am.")
    core.run_loop(lambda: _maybe_run(gmail, cfg), 300)


if __name__ == "__main__":
    run()
