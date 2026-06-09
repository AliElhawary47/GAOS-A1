"""
╔══════════════════════════════════════════════════════════════╗
║   GAOS™ MODULE 02 — Zero-Delay Lead Responder               ║
║   Standalone: £750  |  In: GAOS™ Core, Pro, Enterprise      ║
╠══════════════════════════════════════════════════════════════╣
║   Website form arrives by email → AI drafts a warm,         ║
║   personalised reply → saved as a Gmail draft → owner       ║
║   gets a WhatsApp ping → lead logged to Google Sheets.      ║
║                                                             ║
║   Target client:  Any business with a website contact form  ║
║   Pain solved:    Slow replies losing leads to competitors  ║
╚══════════════════════════════════════════════════════════════╝
"""

import time
import gaos_core as core

log = core.get_logger("lead_catcher")


def build_reply_prompt(lead_email_text, business_name):
    """Asks DeepSeek to draft a warm reply and extract the lead's details."""
    return f"""You are the friendly front-desk assistant for "{business_name}".
A potential customer has submitted this enquiry:

---
{lead_email_text[:2000]}
---

Return ONLY valid JSON with these exact keys:
  LeadName        — the enquirer's name, or "there" if not found
  LeadEnquiry     — a one-line summary of what they want
  LeadScore       — classify as "Hot" (urgent, time-sensitive, or high-value signal),
                    "Warm" (genuine interest, no urgency), or "Cold" (vague, generic,
                    or low-signal)
  SuggestedReply  — a warm, professional 3-4 sentence reply that thanks
                    them, confirms we received their enquiry, and says we
                    will be in touch within a few hours. Sign off as
                    "The {business_name} Team". No placeholders.

Rules: ONLY JSON. No markdown. No backticks."""


GAOS_LEAD_LABEL = "GAOS/Lead"


def process_lead(gmail, cfg, message_id):
    # Claim this email immediately so Module 03 won't double-send an SMS.
    core.gmail_label(gmail, message_id, GAOS_LEAD_LABEL)

    headers, msg = core.gmail_get_message(gmail, message_id)
    sender       = headers.get("From", "Unknown")
    body_text    = core.gmail_get_body_text(msg)

    if not body_text:
        log.warning("Empty lead email. Skipping.")
        core.gmail_mark_read(gmail, message_id)
        return False

    log.info(f"New lead from {sender}")

    business = cfg["business"]["name"]
    data = core.ask_deepseek(cfg["deepseek"]["api_key"], build_reply_prompt(body_text, business))
    if not data:
        log.error("AI draft failed. Skipping.")
        core.gmail_mark_read(gmail, message_id)
        return False

    lead_name = core.safe_text(data.get("LeadName"), "there")
    enquiry   = core.safe_text(data.get("LeadEnquiry"), "General enquiry")
    reply     = core.safe_text(data.get("SuggestedReply"), "Thank you for your enquiry.")
    score     = core.safe_text(data.get("LeadScore"), "Warm")

    # Save the AI reply as a Gmail draft (owner reviews & sends)
    core.gmail_create_draft(gmail, sender, cfg["gmail"]["watch_inbox"],
                            f"Re: Your enquiry to {business}", reply)
    log.info(f"Reply draft saved to Gmail. Lead score: {score}")

    # Log lead to Sheets (score stored in Status column for CoS hot-lead detection)
    core.sheets_append_row(
        cfg["google_sheets"]["sheet_id"],
        cfg["google_sheets"]["tabs"]["leads"],
        [lead_name, sender, enquiry, score, core.timestamp()]
    )

    # Ping the owner on WhatsApp — flag Hot leads prominently
    tw = cfg["twilio"]
    if "YOUR_" not in tw["account_sid"]:
        prefix = "🔥 HOT LEAD" if score == "Hot" else "New lead"
        core.send_whatsapp(
            tw["account_sid"], tw["auth_token"], tw["from_number"], tw["owner_mobile"],
            f"{prefix}: {lead_name} — {enquiry}. A reply draft is ready in your inbox."
        )
        log.info("WhatsApp alert sent to owner.")

    core.gmail_mark_read(gmail, message_id)
    return True



LEAD_QUERY = 'is:unread (subject:enquiry OR subject:"contact form" OR subject:"new submission")'

def scan(gmail, cfg):
    """Called by gaos_engine.py each poll cycle."""
    for e in core.gmail_search(gmail, LEAD_QUERY):
        try:
            process_lead(gmail, cfg, e["id"])
        except Exception as ex:
            log.error(f"Lead scan error: {ex}")


def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 02 - Zero-Delay Lead Responder")
    print("="*60 + "\n")

    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Watching for new website leads. Ctrl+C to stop.\n")

    # Adjust this search to match how the client's form emails arrive.
    # Many form tools put "form submission" or the form name in the subject.
    query = 'is:unread (subject:enquiry OR subject:"contact form" OR subject:"new submission")'

    count = 0
    while True:
        try:
            emails = core.gmail_search(gmail, query)
            for e in emails:
                if process_lead(gmail, cfg, e["id"]):
                    count += 1
                    log.info(f"Lead #{count} handled.\n")
            if not emails:
                log.info(f"No new leads. Next check in {cfg['settings']['check_every_seconds']//60} min.")
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Loop error: {ex}")
        time.sleep(cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
