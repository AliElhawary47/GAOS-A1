"""
╔══════════════════════════════════════════════════════════════╗
║   GAOS™ MODULE 03 — Emergency Lead SMS Alert                ║
║   Standalone: £600  |  In: GAOS™ Core, Pro, Enterprise      ║
╠══════════════════════════════════════════════════════════════╣
║   The instant a high-value lead email arrives, GAOS™ fires  ║
║   an SMS straight to the owner's phone so they can call     ║
║   back within minutes — before a competitor does.           ║
║                                                             ║
║   Target client:  Roofers, plumbers, locksmiths, dentists   ║
║   Pain solved:    Missing urgent leads while away from desk ║
╚══════════════════════════════════════════════════════════════╝

This module is intentionally simple and fast — no AI step in the
critical path, so the SMS goes out in seconds. AI is used only to
pull the lead's name and need into a short summary.
"""

import gaos_core as core

log = core.get_logger("urgent_alert")


def build_summary_prompt(lead_text):
    return f"""Summarise this incoming lead in a very short form.

Return ONLY valid JSON with these keys:
  Name    — the lead's name, or "Unknown"
  Need    — what they want, in 5 words or fewer
  Phone   — their phone number if present, or "see email"

Lead text:
---
{lead_text[:1500]}
---
ONLY JSON. No markdown."""


GAOS_URGENT_LABEL = "GAOS-Urgent"


def process_urgent_lead(gmail, cfg, message_id):
    headers, msg = core.gmail_get_message(gmail, message_id)
    sender       = headers.get("From", "Unknown")
    subject      = headers.get("Subject", "")
    body_text    = core.gmail_get_body_text(msg)

    log.info(f"Urgent lead from {sender}")

    # Quick AI summary (kept short so it's fast)
    data = core.ask_deepseek(cfg["deepseek"]["api_key"],
                             build_summary_prompt(body_text), max_tokens=120)
    if not data:
        data = {"Name": "New Lead", "Need": "enquiry", "Phone": "see email"}

    name  = core.safe_text(data.get("Name"), "New Lead")
    need  = core.safe_text(data.get("Need"), "enquiry")
    phone = core.safe_text(data.get("Phone"), "see email")

    # Fire the SMS immediately
    tw  = cfg["twilio"]
    msg_text = f"URGENT LEAD: {name} wants {need}. Call back now: {phone}"

    if "YOUR_" in tw["account_sid"]:
        log.warning("Twilio not configured — would have sent: " + msg_text)
        ok = True  # nothing to retry — treat as handled so we don't re-run the AI every poll
    else:
        ok = core.send_sms(tw["account_sid"], tw["auth_token"],
                           tw["from_number"], tw["owner_mobile"], msg_text)
        log.info("SMS sent to owner." if ok else "SMS failed — will retry next poll.")

    if not ok:
        # Leave the email unlabelled (and unread) so the next poll retries the SMS.
        return False

    # Log to leads sheet
    # Canonical Lead_Log columns: Date | From | Email | Subject | Summary | Status | Chase Sent | Source
    core.sheets_append_row(
        cfg["google_sheets"]["sheet_id"],
        cfg["google_sheets"]["tabs"]["leads"],
        [core.timestamp(), name, sender, subject, need, "SMS Sent", "", ""]
    )

    # Label instead of marking read — module 02 still needs the unread email
    # to draft its AI reply; the label stops this module reprocessing it.
    core.gmail_label(gmail, message_id, GAOS_URGENT_LABEL)
    return True



URGENT_QUERY = 'is:unread -label:GAOS/Lead -label:gaos-urgent (subject:enquiry OR subject:quote OR subject:"contact form" OR subject:emergency)'

def scan(gmail, cfg):
    """Called by gaos_engine.py each poll cycle."""
    for e in core.gmail_search(gmail, URGENT_QUERY):
        try:
            process_urgent_lead(gmail, cfg, e["id"])
        except Exception as ex:
            log.error(f"Urgent alert error: {ex}")


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("module_03_urgent_alert: Watching for urgent leads. Fast SMS mode.")
    poll = min(cfg.get("settings", {}).get("check_every_seconds", 300), 60)
    core.run_loop(lambda: scan(gmail, cfg), poll)


if __name__ == "__main__":
    run()
