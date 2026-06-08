"""
GAOS™ MODULE 22 — Website Chatbot
Zone 5: Converse | Standalone: £1,400 | In: GAOS™ Pro, Enterprise

An AI chatbot that lives on the client's website. Answers visitor
questions from a knowledge base, captures leads, and books enquiries —
24/7, with no human needed. Runs on the GAOS web server (gaos_server.py),
not the poller. The client embeds one line of JavaScript on their site.

Knowledge base: Google Sheet tab "Chatbot_Knowledge" (Question | Answer)
Captured leads:  logged to the "Lead_Log" tab automatically.

This module provides the handler logic. The server (gaos_server.py)
routes POST /chat requests here. The embeddable widget is widget.js.

Target client: Any business with a website.
Pain solved:   Website visitors leaving because nobody answers instantly.
"""

import gaos_core as core

log = core.get_logger("website_chatbot")

# In-memory conversation store keyed by session id.
# For a small business this is fine; transcripts are logged to Sheets.
_conversations = {}
MAX_HISTORY = 10   # keep last N turns per session


def load_knowledge(cfg):
    """Loads the chatbot knowledge base from Google Sheets."""
    try:
        rows = core.sheets_read_all(
            cfg["google_sheets"]["sheet_id"],
            cfg["google_sheets"]["tabs"].get("chatbot", "Chatbot_Knowledge")
        )
        kb = []
        for r in rows:
            q = str(r.get("Question", "")).strip()
            a = str(r.get("Answer", "")).strip()
            if q and a:
                kb.append(f"Q: {q}\nA: {a}")
        return "\n\n".join(kb)
    except Exception as e:
        log.error(f"Knowledge load failed: {e}")
        return ""


def build_system_prompt(cfg, knowledge):
    business = cfg["business"]["name"]
    return (
        f"You are the friendly website assistant for {business}. "
        f"Answer visitor questions helpfully and concisely using ONLY the "
        f"knowledge base below. If you don't know an answer, say you'll have "
        f"someone follow up and ask for their name and email. Keep replies "
        f"under 60 words, warm and professional.\n\n"
        f"KNOWLEDGE BASE:\n{knowledge}\n\n"
        f"If the visitor shares contact details or wants a quote/callback, "
        f"thank them and confirm someone will be in touch shortly."
    )


def detect_and_log_lead(cfg, session_id, user_message, history):
    """If the visitor shares an email, capture it as a lead."""
    import re
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", user_message)
    if not email_match:
        return
    email = email_match.group(0)

    # Use AI to pull a name and summary from the conversation
    convo_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
    data = core.ask_deepseek(
        cfg["deepseek"]["api_key"],
        f"From this website chat, extract the visitor's name and what they want. "
        f"Return ONLY JSON keys: Name, Interest.\n\n{convo_text}",
        max_tokens=100
    ) or {}

    core.sheets_append_row(
        cfg["google_sheets"]["sheet_id"],
        cfg["google_sheets"]["tabs"].get("leads", "Lead_Log"),
        [core.safe_text(data.get("Name"), "Website visitor"), email,
         core.safe_text(data.get("Interest"), "Website chat enquiry"),
         "Chatbot Lead", core.timestamp()]
    )
    log.info(f"Chatbot captured lead: {email}")


def handle_message(cfg, session_id, user_message):
    """
    Main entry point called by gaos_server.py for each chat message.
    Returns the assistant's reply text.
    """
    knowledge = load_knowledge(cfg)

    # Retrieve or start this session's history
    history = _conversations.get(session_id, [])
    history.append({"role": "user", "content": user_message})

    # Generate reply with full conversation context
    reply = core.chat_deepseek(
        cfg["deepseek"]["api_key"],
        history[-MAX_HISTORY:],
        system_prompt=build_system_prompt(cfg, knowledge),
        max_tokens=200
    )

    history.append({"role": "assistant", "content": reply})
    _conversations[session_id] = history[-MAX_HISTORY:]

    # Capture lead if an email appeared
    detect_and_log_lead(cfg, session_id, user_message, history)

    return reply


# This module has no run() loop — it is served by gaos_server.py.
# This stub lets the launcher report it clearly if called directly.
def run():
    print("\nModule 22 (Website Chatbot) runs via the GAOS web server.")
    print("Start it with:  python gaos_server.py\n")


if __name__ == "__main__":
    run()
