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

from datetime import datetime
import gaos_core as core

log = core.get_logger("newsletter_mailer")

RUN_WEEKDAY = 0   # Monday
RUN_HOUR    = 9
RUN_DAY_MAX = 7   # first Monday = day 1-7 of the month


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
        email  = str(row.get("Email", "")).strip()
        name   = str(row.get("Name",  "")).strip()
        status = str(row.get("Status", "")).strip().lower()
        if not email:
            continue
        # Never newsletter churned / opted-out clients
        if status in ("churned", "inactive", "cancelled", "lost",
                      "do not contact", "do-not-contact", "left"):
            continue
        personalised = f"Dear {name},\n\n{body}" if name else body
        if core.gmail_send(gmail, email, cfg["gmail"]["watch_inbox"],
                           subject, personalised):
            sent += 1

    return sent, subject


def _month_matches(month_cell: str) -> bool:
    """True when a hand-typed Month cell means the current month.
    Accepts '2026-06', '2026-06-01', 'June 2026', 'Jun 2026'."""
    text = str(month_cell).strip()
    if not text:
        return False
    if text[:7] == datetime.now().strftime("%Y-%m"):
        return True
    for fmt in ("%B %Y", "%b %Y"):
        try:
            dt = datetime.strptime(text, fmt)
            return (dt.year, dt.month) == (datetime.now().year,
                                           datetime.now().month)
        except ValueError:
            continue
    return False


def run_newsletter(gmail, cfg):
    sheet_id   = cfg["google_sheets"]["sheet_id"]
    tab        = cfg["google_sheets"]["tabs"].get("newsletter_queue", "Newsletter_Queue")
    month_str  = datetime.now().strftime("%B %Y")
    rows       = core.sheets_read_all(sheet_id, tab)

    # Find this month's pending newsletter ("sending" excluded too, so a
    # process restart mid-send can never blast every client twice)
    pending = [r for r in rows
               if str(r.get("Status","")).strip().lower() not in ("sent","skip","sending")
               and _month_matches(r.get("Month",""))]

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

    # Claim the row before the send loop so a crash/restart can't double-send
    idx = rows.index(row)
    core.sheets_update_cell(sheet_id, tab, idx + 2, "Status", "Sending")

    count, subject = send_newsletter(gmail, cfg, newsletter)
    log.info(f"Newsletter '{subject}' sent to {count} clients.")

    core.sheets_update_cell(sheet_id, tab, idx + 2, "Status", "Sent")
    core.sheets_update_cell(sheet_id, tab, idx + 2, "Sent At", core.timestamp())


def _tick(gmail, cfg):
    if core.should_run_at(RUN_HOUR, weekday=RUN_WEEKDAY) and datetime.now().day <= RUN_DAY_MAX:
        run_newsletter(gmail, cfg)


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Scheduled: first Monday of every month at 9am. Ctrl+C to stop.")
    core.run_loop(lambda: _tick(gmail, cfg),
                  cfg.get("settings", {}).get("check_every_seconds", 300))


if __name__ == "__main__":
    run()
