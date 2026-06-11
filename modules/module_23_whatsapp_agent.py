"""
GAOS™ MODULE 23 — WhatsApp AI Agent
Zone 5: Converse | Standalone: £1,600 | In: GAOS™ Core, Pro, Enterprise

A two-way conversational AI inside WhatsApp Business. When a customer
messages the business number, GAOS reads it, replies intelligently from
the knowledge base, qualifies the lead, and escalates to the human owner
only when genuinely needed. Runs on the GAOS web server.

Powered by Twilio's WhatsApp Business API (incoming messages arrive as a
webhook at POST /whatsapp). Conversation memory is keyed by phone number.

Knowledge base: Google Sheet tab "Chatbot_Knowledge" (shared with Module 22)
Escalations:    logged to "Lead_Log", owner pinged via SMS.

Target client: Any business that gets WhatsApp enquiries.
Pain solved:   Slow WhatsApp replies and after-hours messages going unanswered.
"""

import gaos_core as core
# Chief of Staff integration — route business intelligence queries to Module 35
try:
    from modules import module_35_chief_of_staff as _cos
    _COS_AVAILABLE = True
except ImportError:
    _COS_AVAILABLE = False


log = core.get_logger("whatsapp_agent")

_conversations = {}        # keyed by sender phone number
MAX_HISTORY  = 10
MAX_SESSIONS = 500         # evict oldest senders beyond this (memory cap)
ESCALATE_FLAG = "[ESCALATE]"


def _store_history(sender, history):
    """Saves a sender's history, evicting the oldest when the cap is hit."""
    _conversations.pop(sender, None)
    _conversations[sender] = history[-MAX_HISTORY:]
    while len(_conversations) > MAX_SESSIONS:
        _conversations.pop(next(iter(_conversations)))




def build_system_prompt(cfg, knowledge):
    business = cfg["business"]["name"]
    return (
        f"You are the WhatsApp assistant for {business}. Reply to customer "
        f"messages helpfully and concisely using the knowledge base below. "
        f"WhatsApp style: short, friendly, no long paragraphs. "
        f"If the customer needs something you cannot handle (complaint, complex "
        f"quote, urgent issue, or asks for a human), end your reply with the exact "
        f"token {ESCALATE_FLAG} so a team member is alerted. Otherwise never show "
        f"that token.\n\nKNOWLEDGE BASE:\n{knowledge}"
    )


def escalate(cfg, sender, history):
    """Alerts the human owner via SMS that a conversation needs them."""
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])

    summary = core.ask_deepseek(
        cfg["deepseek"]["api_key"],
        f"Summarise this WhatsApp chat in one line for the business owner. "
        f"Return ONLY JSON key: Summary.\n\n{convo}",
        max_tokens=80
    ) or {}
    note = core.safe_text(summary.get("Summary"), "Customer needs assistance")

    tw = cfg["twilio"]
    if "YOUR_" not in tw["account_sid"]:
        core.send_sms(tw["account_sid"], tw["auth_token"], tw["from_number"],
                      tw["owner_mobile"],
                      f"WhatsApp escalation from {sender}: {note}")

    core.sheets_append_row(
        cfg["google_sheets"]["sheet_id"],
        cfg["google_sheets"]["tabs"].get("leads", "Lead_Log"),
        [sender, sender, note, "WhatsApp Escalation", core.timestamp()]
    )
    log.info(f"Escalated WhatsApp conversation from {sender}")


def handle_message(cfg, sender, body):
    """
    Called by gaos_server.py for each incoming WhatsApp message.
    `sender` is the phone number, `body` is the message text.
    Returns the reply text to send back via WhatsApp.
    """
    knowledge = core.load_chatbot_knowledge(cfg)
    history = _conversations.get(sender, [])
    history.append({"role": "user", "content": body})

    if _COS_AVAILABLE:
        try:
            if _cos.handle_if_cos_query(None, cfg, body, sender):
                return "Got it — pulling your briefing now. One moment."
        except Exception:
            pass

    reply = core.chat_deepseek(
        cfg["deepseek"]["api_key"],
        history[-MAX_HISTORY:],
        system_prompt=build_system_prompt(cfg, knowledge),
        max_tokens=200
    )

    # Check for escalation token
    if ESCALATE_FLAG in reply:
        reply = reply.replace(ESCALATE_FLAG, "").strip()
        escalate(cfg, sender, history + [{"role": "assistant", "content": reply}])
        reply += "\n\nI've let our team know — someone will be in touch very soon."

    history.append({"role": "assistant", "content": reply})
    _store_history(sender, history)
    return reply


def run():
    print("\nModule 23 (WhatsApp Agent) runs via the GAOS web server.")
    print("Start it with:  python gaos_server.py\n")


if __name__ == "__main__":
    run()
