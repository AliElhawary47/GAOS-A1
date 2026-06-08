"""
GAOS™ MODULE 32 — Newsletter Mailer
Virtual Marketer | £199/mo bundle | Standalone: £750

On the first Monday of every month, reads bullet points and topics
from a Newsletter_Queue sheet, uses AI to write a professional
newsletter in the business's voice, and emails it to every active
client on the Clients list.

The owner never writes a newsletter. They add a few bullet points
to a sheet. GAOS does the rest.

Sheet tab required: Newsletter_Queue
Columns: Month | Topics (bullet points) | Tone | Status | Sent At

Target: Any business wanting consistent email marketing without
        the time cost. Agencies, consultants, clinics, trades.
Pain:   "We keep meaning to send a newsletter but never get round to it."
"""

import time
from datetime import datetime
import gaos_core as core

log = core.get_logger("newsletter_mailer")

RUN_WEEKDAY = 0   # Monday
RUN_HOUR    = 9
RUN_DAY_MAX = 7   # first Monday = day 1-7 of the month


def is_run_time():
    now = datetime.now()
    return (now.weekday() == RUN_WEEKDAY
            and now.hour == RUN_HOUR
            and now.minute < 5
            and now.day <= RUN_DAY_MAX)


def build_newsletter_prompt(business_name, topics, tone, month_str):
    tone_guide = tone.strip() if tone and tone.strip() else "professional and warm"
    return (
        f"Write a monthly email newsletter for {business_name} for {month_str}.\n"
        f"Tone: {tone_guide}\n"
        f"Topics and bullet points from the team:\n{topics}\n\n"
        f"Format:\n"
        f"- Subject line (write: Subject: ...)\n"
        f"- Greeting\n"
        f"- 2-3 short paragraphs covering the topics naturally\n"
        f"- A brief closing with a call to action (reply, book, call)\n"
        f"- Sign-off as {business_name}\n\n"
        f"Keep it under 250 words. Friendly, not salesy. "
        f"Return ONLY the email text starting with 'Subject:'."
    )


def send_newsletter(gmail, cfg, newsletter_text):
    """Sends the newsletter to all active clients."""
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("clients", "Clients")
    rows     = core.sheets_read_all(sheet_id, tab)

    # Extract subject from AI output
    lines   = newsletter_text.strip().split("\n")
    subject = "Monthly Update"
    body    = newsletter_text
    if lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body    = "\n".join(lines[1:]).strip()

    sent = 0
    for row in rows:
        email = str(row.get("Email", "")).strip()
        name  = str(row.get("Name",  "")).strip()
        if not email:
            continue
        personalised = f"Dear {name},\n\n{body}" if name else body
        core.gmail_send(gmail, email, cfg["gmail"]["watch_inbox"],
                        subject, personalised)
        sent += 1

    return sent, subject


def run_newsletter(gmail, cfg):
    sheet_id   = cfg["google_sheets"]["sheet_id"]
    tab        = cfg["google_sheets"]["tabs"].get("newsletter_queue", "Newsletter_Queue")
    month_str  = datetime.now().strftime("%B %Y")
    rows       = core.sheets_read_all(sheet_id, tab)

    # Find this month's pending newsletter
    pending = [r for r in rows
               if str(r.get("Status","")).strip().lower() not in ("sent","skip")
               and str(r.get("Month","")).strip()[:7] == datetime.now().strftime("%Y-%m")]

    if not pending:
        log.info(f"No newsletter queued for {month_str}.")
        return

    row    = pending[0]
    topics = str(row.get("Topics","")).strip()
    tone   = str(row.get("Tone","professional and warm")).strip()

    if not topics:
        log.warning("Newsletter_Queue row has no topics. Add bullet points to the Topics column.")
        return

    log.info(f"Writing {month_str} newsletter...")
    newsletter = core.ask_deepseek(
        cfg["deepseek"]["api_key"],
        build_newsletter_prompt(cfg["business"]["name"], topics, tone, month_str),
        max_tokens=400,
        expect_json=False
    )

    if not newsletter:
        log.error("AI failed to generate newsletter.")
        return

    count, subject = send_newsletter(gmail, cfg, newsletter)
    log.info(f"Newsletter '{subject}' sent to {count} clients.")

    # Mark as sent
    idx = rows.index(row)
    core.sheets_update_cell(sheet_id, tab, idx + 2, 4, "Sent")
    core.sheets_update_cell(sheet_id, tab, idx + 2, 5, core.timestamp())


def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 32 — Newsletter Mailer")
    print("="*60 + "\n")
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Scheduled: first Monday of every month at 9am. Ctrl+C to stop.\n")

    while True:
        try:
            if is_run_time():
                run_newsletter(gmail, cfg)
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Error: {ex}")
        time.sleep(300)


if __name__ == "__main__":
    run()
