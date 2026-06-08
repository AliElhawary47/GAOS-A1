"""
╔══════════════════════════════════════════════════════════════╗
║   GAOS™ MODULE 06 — Smart FAQ Mailbox Assistant             ║
║   Standalone: £950  |  In: GAOS™ Enterprise                 ║
╠══════════════════════════════════════════════════════════════╣
║   Reads incoming customer emails, checks them against the   ║
║   business's FAQ knowledge base, and if it can answer with  ║
║   high confidence, drafts the perfect reply in Gmail for    ║
║   staff to approve and send with one click.                 ║
║                                                             ║
║   Target client:  E-commerce, clinics, support-heavy firms  ║
║   Pain solved:    Hours wasted answering the same questions  ║
╚══════════════════════════════════════════════════════════════╝

The FAQ knowledge base lives in a Google Sheet tab
(FAQ_Knowledge_Base) with two columns:
  A: Question | B: Answer
GAOS reads these and uses them as the AI's source of truth.
"""

import gaos_core as core

log = core.get_logger("faq_reply")


def load_faqs(cfg):
    """Loads the FAQ knowledge base from Google Sheets."""
    rows = core.sheets_read_all(
        cfg["google_sheets"]["sheet_id"],
        cfg["google_sheets"]["tabs"]["faq"]
    )
    faqs = []
    for r in rows:
        q = str(r.get("Question", "")).strip()
        a = str(r.get("Answer", "")).strip()
        if q and a:
            faqs.append(f"Q: {q}\nA: {a}")
    return "\n\n".join(faqs)


def build_prompt(customer_email, faq_text, business_name):
    return f"""You are a customer support assistant for "{business_name}".
Below is the company's FAQ knowledge base, then a customer email.

KNOWLEDGE BASE:
{faq_text}

CUSTOMER EMAIL:
---
{customer_email[:1500]}
---

Decide if the knowledge base can confidently answer this email.

Return ONLY valid JSON with these keys:
  CanAnswer   — true or false (boolean). True ONLY if you are 90%+ confident
                the answer is in the knowledge base above.
  DraftReply  — if CanAnswer is true, a warm, complete reply answering their
                question, signed off as "The {business_name} Team".
                If CanAnswer is false, an empty string "".

ONLY JSON. No markdown. No backticks."""


def process_email(gmail, cfg, faq_text, message_id):
    headers, msg = core.gmail_get_message(gmail, message_id)
    sender       = headers.get("From", "Unknown")
    subject      = headers.get("Subject", "your enquiry")
    body_text    = core.gmail_get_body_text(msg)

    if not body_text:
        core.gmail_mark_read(gmail, message_id)
        return False

    business = cfg["business"]["name"]
    data = core.ask_deepseek(cfg["deepseek"]["api_key"],
                             build_prompt(body_text, faq_text, business))

    if not data:
        log.warning("AI check failed. Leaving email unread for staff.")
        return False

    can_answer = data.get("CanAnswer", False)
    draft      = core.safe_text(data.get("DraftReply"), "")

    if can_answer and draft:
        core.gmail_create_draft(gmail, sender, cfg["gmail"]["watch_inbox"],
                                f"Re: {subject}", draft)
        log.info(f"FAQ match — draft reply saved for: {sender}")
        # Mark read since we've handled it (draft is ready)
        core.gmail_mark_read(gmail, message_id)
        return True
    else:
        # Not an FAQ — leave it unread so a human handles it
        log.info(f"No confident FAQ match for {sender} — left for staff.")
        return False



FAQ_QUERY = "is:unread -subject:enquiry -subject:invoice -has:attachment"

def scan(gmail, cfg):
    """Called by gaos_engine.py each poll cycle. Reloads FAQs each cycle."""
    faq_text = load_faqs(cfg)
    for e in core.gmail_search(gmail, FAQ_QUERY):
        try:
            process_email(gmail, cfg, faq_text, e["id"])
        except Exception as ex:
            log.error(f"FAQ reply error: {ex}")


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("module_06_faq_reply: Watching inbox for answerable questions.")
    core.run_loop(lambda: scan(gmail, cfg),
                  cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
