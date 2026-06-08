"""
GAOS™ MODULE 20 — Licence & Expiry Alert
Zone 4: Schedule | Standalone: £700 | In: GAOS™ Pro, Enterprise

Daily check of a Licences sheet. When any item (insurance policy,
software licence, vehicle MOT, gas certificate, etc.) is within the
alert window before expiry, GAOS sends an email alert and marks it.

Sheet tab required: Licences
Columns: Description | Expiry Date | Alert Days Before | Owner Email | Status | Alerted

Target client: Trades companies, fleet businesses, property managers, any regulated business.
Pain solved:   Letting a critical licence or insurance lapse through oversight.
"""

import time
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("expiry_alert")

CHECK_HOUR = 9
ALERT_COL  = 6   # "Alerted" column (1-based)


def is_check_time():
    now = datetime.now()
    return now.hour == CHECK_HOUR and now.minute < 5


def check_expiries(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("licences", "Licences")
    rows     = core.sheets_read_all(sheet_id, tab)
    today    = datetime.now().date()
    alerted  = 0

    for i, row in enumerate(rows):
        description = str(row.get("Description",      "")).strip()
        expiry_str  = str(row.get("Expiry Date",      "")).strip()[:10]
        alert_days  = int(str(row.get("Alert Days Before", "30")).strip() or "30")
        owner_email = str(row.get("Owner Email",      "")).strip()
        status      = str(row.get("Status",           "active")).strip().lower()
        alerted_v   = str(row.get("Alerted",          "")).strip().lower()

        if status in ("expired", "cancelled", "renewed") or alerted_v == "sent":
            continue

        try:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        days_remaining = (expiry_date - today).days

        if days_remaining <= 0:
            subject = f"URGENT: {description} has EXPIRED"
            body = (f"IMPORTANT: {description} expired on "
                    f"{expiry_date.strftime('%d %B %Y')} — "
                    f"immediate action required.")
        elif days_remaining <= alert_days:
            subject = f"Reminder: {description} expires in {days_remaining} days"
            body = (f"This is an automated reminder that {description} "
                    f"is due to expire on {expiry_date.strftime('%d %B %Y')} "
                    f"({days_remaining} days from today).\n\n"
                    f"Please arrange renewal as soon as possible.")
        else:
            continue

        recipient = owner_email or cfg["gmail"]["alert_email"]
        full_body  = f"{body}\n\nAether Frameworks — GAOS™ Expiry Alert"

        core.gmail_send(gmail, recipient, cfg["gmail"]["watch_inbox"], subject, full_body)
        core.sheets_update_cell(sheet_id, tab, i + 2, ALERT_COL, core.timestamp())
        log.info(f"Expiry alert sent: {description} ({days_remaining} days left)")
        alerted += 1

    return alerted


def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 20 - Licence & Expiry Alert")
    print("="*60 + "\n")
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info(f"Scheduled: daily at {CHECK_HOUR}:00am. Ctrl+C to stop.\n")

    while True:
        try:
            if is_check_time():
                n = check_expiries(gmail, cfg)
                log.info(f"Sent {n} expiry alert(s)." if n else "No items expiring soon.")
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Error: {ex}")
        time.sleep(300)


if __name__ == "__main__":
    run()
