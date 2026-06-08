"""
GAOS™ MODULE 13 — Daily Digest
Zone 3: Report | Standalone: £700 | In: GAOS™ Pro, Enterprise

Every morning at 8am, emails the business owner a clean plain-English
summary of the previous day's activity — new leads, invoices received,
jobs completed, and anything else logged in the GAOS sheets.

No data is stored or aggregated externally. Reads directly from the
client's own Google Sheets. Zero cost to run.

Target client: Any business owner who wants visibility without logging in.
Pain solved:   Spending the first hour of every day piecing together what happened.
"""

import time
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("daily_digest")

DIGEST_HOUR = 8   # send at 8:00am


def is_digest_time():
    now = datetime.now()
    return now.hour == DIGEST_HOUR and now.minute < 5


def count_todays_rows(rows, date_col_name, target_date_str):
    """Count rows that were logged on the target date."""
    return sum(1 for r in rows if str(r.get(date_col_name, "")).startswith(target_date_str))


def build_digest_prompt(summary_data, business_name):
    return f"""You are a business analyst writing a daily briefing for the owner of {business_name}.

Here is yesterday's raw activity data:
{summary_data}

Write a friendly, clear, plain-English daily digest email. Include:
- A one-line opening greeting mentioning the date
- Key highlights (what happened, any numbers worth noting)
- Any items that might need the owner's attention today
- A brief positive closing line

Keep it under 200 words. Professional but warm tone.
Return ONLY the email body text. No subject line. No JSON."""


def generate_digest(gmail, cfg):
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    sheet_id  = cfg["google_sheets"]["sheet_id"]
    tabs      = cfg["google_sheets"]["tabs"]
    business  = cfg["business"]["name"]

    # Gather counts from each sheet tab
    summary_parts = [f"Date: {yesterday}", f"Business: {business}", ""]

    tab_map = {
        "invoices": ("Invoice_Log",  "Logged At",  "Invoices received"),
        "leads":    ("Lead_Log",     "Logged At",  "New leads"),
        "reviews":  ("Completed_Jobs","Logged At", "Jobs completed"),
        "contracts":("Contract_Log", "Logged At",  "Contracts sent"),
    }

    for key, (default_tab, date_col, label) in tab_map.items():
        tab_name = tabs.get(key, default_tab)
        try:
            rows  = core.sheets_read_all(sheet_id, tab_name)
            count = count_todays_rows(rows, date_col, yesterday)
            summary_parts.append(f"{label}: {count}")
        except Exception:
            summary_parts.append(f"{label}: (data unavailable)")

    summary_data = "\n".join(summary_parts)
    log.info(f"Building digest for {yesterday}")

    # Use AI to write the digest in plain English
    body = core.ask_deepseek(
        cfg["deepseek"]["api_key"],
        build_digest_prompt(summary_data, business),
        max_tokens=300,
        expect_json=False
    )

    if not body:
        # Fallback: plain text summary without AI
        body = f"Daily Digest — {yesterday}\n\n" + summary_data

    core.gmail_send(
        gmail,
        cfg["gmail"]["alert_email"],
        cfg["gmail"]["watch_inbox"],
        f"GAOS Daily Digest — {yesterday}",
        body
    )
    log.info("Daily digest sent.")


def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 13 - Daily Digest")
    print("="*60 + "\n")
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info(f"Scheduled to run at {DIGEST_HOUR}:00 every morning. Ctrl+C to stop.\n")

    while True:
        try:
            if is_digest_time():
                generate_digest(gmail, cfg)
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Digest error: {ex}")
        time.sleep(300)   # check every 5 minutes


if __name__ == "__main__":
    run()
