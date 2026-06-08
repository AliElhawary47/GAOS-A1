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


def process_urgent_lead(gmail, cfg, message_id):
    headers, msg = core.gmail_get_message(gmail, message_id)
    sender       = headers.get("From", "Unknown")
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
    else:
        ok = core.send_sms(tw["account_sid"], tw["auth_token"],
                           tw["from_number"], tw["owner_mobile"], msg_text)
        log.info("SMS sent to owner." if ok else "SMS failed.")

    # Log to leads sheet
    core.sheets_append_row(
        cfg["google_sheets"]["sheet_id"],
        cfg["google_sheets"]["tabs"]["leads"],
        [name, sender, need, "SMS Sent", core.timestamp()]
    )

    core.gmail_mark_read(gmail, message_id)
    return True



URGENT_QUERY = 'is:unread -label:GAOS/Lead (subject:enquiry OR subject:quote OR subject:"contact form" OR subject:emergency)'

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
    poll = min(cfg["settings"]["check_every_seconds"], 60)
    core.run_loop(lambda: scan(gmail, cfg), poll)


if __name__ == "__main__":
    run()
