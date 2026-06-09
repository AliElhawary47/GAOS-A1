"""
GAOS™ MODULE 21 — Re-Engagement Mailer
Zone 4: Schedule | Standalone: £750 | In: GAOS™ Enterprise

Weekly check of the Clients sheet for clients who haven't been
active for a configurable number of days. Sends a warm, personalised
check-in email using AI to re-open the conversation.

Sheet tab required: Clients
Columns: Name | Email | Last Contact Date | Re-Engaged | Notes

Target client: Any service business — gyms, consultants, clinics, agencies.
Pain solved:   Quietly losing clients who just drifted away because nobody reached out.
"""

from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("reengagement_mailer")

CHECK_HOUR         = 10
CHECK_WEEKDAY      = 0    # Monday
INACTIVE_DAYS      = 90   # trigger after this many days of silence
REENGAGED_COL      = 4    # "Re-Engaged" column


def build_reengage_prompt(client_name, business_name, notes):
    note_context = f" We last noted: {notes}." if notes else ""
    return (
        f"Write a warm, genuine re-engagement email from {business_name} to {client_name}."
        f"{note_context}\n"
        f"The client hasn't been active for a while. The email should:\n"
        f"- Check how they are doing\n"
        f"- Mention we've been thinking of them\n"
        f"- Gently suggest reconnecting\n"
        f"- Be 3-4 sentences max, natural and human\n"
        f"Sign off as {business_name}. Return ONLY the email body."
    )


def run_reengage_check(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("clients", "Clients")
    rows     = core.sheets_read_all(sheet_id, tab)
    today    = datetime.now()
    sent     = 0

    for i, row in enumerate(rows):
        name        = str(row.get("Name",              "")).strip()
        email       = str(row.get("Email",             "")).strip()
        last_str    = str(row.get("Last Contact Date", "")).strip()[:10]
        re_engaged  = str(row.get("Re-Engaged",        "")).strip().lower()
        notes       = str(row.get("Notes",             "")).strip()

        status = str(row.get("Status", "active")).strip().lower()
        if not email or not name or re_engaged == "sent":
            continue
        if status in ("churned", "inactive", "cancelled", "lost", "do not contact"):
            log.info(f"Skipping {name} — status: {status}")
            continue

        try:
            last_contact = datetime.strptime(last_str, "%Y-%m-%d")
        except ValueError:
            continue

        if (today - last_contact).days < INACTIVE_DAYS:
            continue

        log.info(f"Re-engaging {name} (last contact: {last_str})")

        body = core.ask_deepseek(
            cfg["deepseek"]["api_key"],
            build_reengage_prompt(name, cfg["business"]["name"], notes),
            max_tokens=150,
            expect_json=False
        )

        if not body:
            body = (f"Hi {name},\n\nWe've been thinking of you and wanted "
                    f"to check in. Hope everything is going well!\n\n"
                    f"Best regards,\n{cfg['business']['name']}")

        core.gmail_send(gmail, email, cfg["gmail"]["watch_inbox"],
                        f"Checking in — {cfg['business']['name']}", body)

        core.sheets_update_cell(sheet_id, tab, i + 2, REENGAGED_COL, core.timestamp())
        sent += 1

    return sent


def _tick(gmail, cfg):
    if core.should_run_at(CHECK_HOUR, weekday=CHECK_WEEKDAY):
        n = run_reengage_check(gmail, cfg)
        log.info(f"Re-engaged {n} inactive client(s)." if n else "No inactive clients to contact.")


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info(f"Scheduled: every Monday at {CHECK_HOUR}:00. Ctrl+C to stop.")
    core.run_loop(lambda: _tick(gmail, cfg), cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
