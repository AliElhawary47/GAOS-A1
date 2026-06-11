"""
GAOS™ MODULE 10 — Appointment Reminder
Zone 2: Chase | Standalone: £650 | In: GAOS™ Core, Pro, Enterprise

Reads an Appointments sheet and automatically sends a reminder
SMS and/or email to clients 24 hours before and again 2 hours before
their appointment. Marks each reminder as sent so it is never duplicated.

Sheet tab required: Appointments
Columns: Date | Time | Client | Email | Phone | Service | Status | 24h Sent | 2h Sent | No_Show_Sent

Target client: Clinics, salons, consultants, personal trainers, dentists.
Pain solved:   No-shows and last-minute cancellations from forgotten appointments.
"""

from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("appointment_reminder")

RESCHEDULE_KEYWORDS = ("reschedule", "rearrange", "cancel", "can't make",
                       "cannot make", "unable to attend", "need to move")


def _client_requested_reschedule(gmail, email: str) -> bool:
    """Returns True if the client emailed in the last 72h about rescheduling."""
    if not email:
        return False
    try:
        query   = f"from:{email} newer_than:3d"
        results = core.gmail_search(gmail, query, max_results=5)
        for msg in results:
            _, body = core.gmail_get_message(gmail, msg["id"])
            if any(kw in body.lower() for kw in RESCHEDULE_KEYWORDS):
                return True
    except Exception:
        pass
    return False


def parse_appt_dt(date_str, time_str):
    """Parse appointment date and time from sheet strings."""
    date_dt = core.parse_date(date_str)
    if not date_dt:
        return None
    try:
        time_part = datetime.strptime(str(time_str).strip()[:5], "%H:%M")
        return date_dt.replace(hour=time_part.hour, minute=time_part.minute)
    except Exception:
        return None


def send_reminder(gmail, cfg, client, mobile, email, appt_dt, reminder_type):
    """Sends SMS and/or email reminder. Returns True if at least one send succeeded."""
    business = cfg["business"]["name"]
    time_str = appt_dt.strftime("%I:%M %p on %A %d %B")
    prefix   = "This is a reminder" if reminder_type == "24h" else "Your appointment is in 2 hours"

    msg = (f"Hi {client}, {prefix} — you have an appointment with "
           f"{business} at {time_str}. Reply STOP to opt out.")

    delivered = False

    # SMS
    tw = cfg["twilio"]
    if mobile and "YOUR_" not in tw["account_sid"]:
        if core.send_sms(tw["account_sid"], tw["auth_token"],
                         tw["from_number"], mobile, msg):
            delivered = True
            log.info(f"Reminder SMS sent to {client} ({mobile})")

    # Email backup
    if email:
        if core.gmail_send(gmail, email, cfg["gmail"]["watch_inbox"],
                           f"Appointment reminder — {business}",
                           f"Dear {client},\n\n{msg}\n\nBest regards,\n{business}"):
            delivered = True
            log.info(f"Reminder email sent to {client} ({email})")

    return delivered


def check_appointments(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("appointments", "Appointments")
    rows     = core.sheets_read_all(sheet_id, tab)
    now      = datetime.now()
    sent     = 0

    for i, row in enumerate(rows):
        status   = str(row.get("Status",     "confirmed")).strip().lower()
        sent_24h = str(row.get("24h Sent",   "")).strip().lower()
        sent_2h  = str(row.get("2h Sent",    "")).strip().lower()
        client   = str(row.get("Client",     "")).strip()
        mobile   = str(row.get("Phone",      "")).strip()
        email    = str(row.get("Email",      "")).strip()
        date_str = str(row.get("Date",       "")).strip()
        time_str = str(row.get("Time",       "09:00")).strip()

        if status in ("cancelled", "completed") or not client:
            continue

        appt_dt = parse_appt_dt(date_str, time_str)
        if not appt_dt:
            continue

        hours_until = (appt_dt - now).total_seconds() / 3600

        # Check for client reschedule/cancel request before sending any reminder
        if (sent_24h != "sent" or sent_2h != "sent") and email:
            if _client_requested_reschedule(gmail, email):
                log.info(f"Reschedule request detected from {client} — flagging row")
                core.sheets_update_cell(sheet_id, tab, i + 2, "Status", "Reschedule Requested")
                continue

        # 24-hour reminder window: between 25h and 23h before
        if 23 <= hours_until <= 25 and sent_24h != "sent":
            if send_reminder(gmail, cfg, client, mobile, email, appt_dt, "24h"):
                core.sheets_update_cell(sheet_id, tab, i + 2, "24h Sent", "Sent")
                sent += 1

        # 2-hour reminder window: between 2.5h and 1.5h before
        if 1.5 <= hours_until <= 2.5 and sent_2h != "sent":
            if send_reminder(gmail, cfg, client, mobile, email, appt_dt, "2h"):
                core.sheets_update_cell(sheet_id, tab, i + 2, "2h Sent", "Sent")
                sent += 1

    return sent


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("module_10_appointment_reminder: Watching appointments sheet.")
    poll = min(cfg.get("settings", {}).get("check_every_seconds", 300), 1800)
    core.run_loop(lambda: check_appointments(gmail, cfg), poll)


if __name__ == "__main__":
    run()
