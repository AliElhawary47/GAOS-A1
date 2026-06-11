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

from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("daily_digest")

DIGEST_HOUR = 8   # send at 8:00am


def count_todays_rows(rows, date_col_name, target_date_str):
    """Count rows that were logged on the target date."""
    count = 0
    for r in rows:
        dt = core.parse_date(r.get(date_col_name, ""))
        if dt and dt.strftime("%Y-%m-%d") == target_date_str:
            count += 1
    return count


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
        "invoices": ("Invoice_Log",  "Invoice Date", "Invoices received"),
        "leads":    ("Lead_Log",     "Date",         "New leads"),
        "reviews":  ("Completed_Jobs","Date",        "Jobs completed"),
        "contracts":("Contract_Log", "Date",         "Contracts sent"),
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

    # Also post a condensed version to Slack if webhook is configured
    slack_url = cfg.get("slack", {}).get("webhook_url", "")
    if slack_url and "YOUR_" not in slack_url:
        slack_body = "\n".join(body.splitlines()[:12])
        core.post_to_slack(slack_url, f"*GAOS Daily Digest — {yesterday}*\n{slack_body}")
        log.info("Daily digest also posted to Slack.")

    log.info("Daily digest sent.")


def _maybe_run(gmail, cfg):
    if core.should_run_at(DIGEST_HOUR):
        generate_digest(gmail, cfg)


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info(f"module_13_daily_digest: Scheduled daily at {DIGEST_HOUR}:00.")
    core.run_loop(lambda: _maybe_run(gmail, cfg), 300)


if __name__ == "__main__":
    run()
