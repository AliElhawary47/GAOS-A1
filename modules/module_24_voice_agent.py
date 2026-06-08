"""
GAOS™ MODULE 24 — AI Voice Agent
Zone 5: Converse | Standalone: £2,200 | In: GAOS™ Enterprise

An AI that answers the phone. It greets the caller, understands what they
need, answers from the knowledge base, captures their details, and sends
the owner an SMS summary of every call. Perfect for capturing out-of-hours
calls that would otherwise be lost to a competitor.

Powered by Twilio Voice (TwiML) + DeepSeek. Runs on the GAOS web server:
  POST /voice         → initial greeting (returns TwiML)
  POST /voice/handle  → processes each spoken reply (returns TwiML)

Knowledge base: shared "Chatbot_Knowledge" tab.
Call summaries: SMS to owner + logged to "Lead_Log".

Target client: Trades, dental, property — anyone who misses calls.
Pain solved:   Missed calls = lost jobs. GAOS answers every time.
"""

import gaos_core as core

log = core.get_logger("voice_agent")

_calls = {}          # keyed by Twilio CallSid → conversation history
MAX_TURNS = 8




def build_system_prompt(cfg, knowledge):
    business = cfg["business"]["name"]
    return (
        f"You are the phone receptionist for {business}. You are speaking out "
        f"loud to a caller, so keep replies to ONE or TWO short sentences — no "
        f"lists, no long explanations. Be warm and natural. Answer from the "
        f"knowledge base below. Your goals: understand why they called, answer "
        f"their question, and if they want a quote or callback, get their name "
        f"and confirm the business will call them back. When the caller's need "
        f"is fully handled, end your reply with the token [END].\n\n"
        f"KNOWLEDGE BASE:\n{knowledge}"
    )


def greeting(cfg, call_sid):
    """First TwiML when a call connects."""
    business = cfg["business"]["name"]
    _calls[call_sid] = []
    text = (f"Hello, thank you for calling {business}. "
            f"How can I help you today?")
    base = cfg.get("server", {}).get("public_url", "")
    return core.twiml_gather(text, f"{base}/voice/handle")


def handle_turn(cfg, call_sid, caller_number, speech_text):
    """
    Processes one spoken turn. Returns TwiML for the next step.
    Called by gaos_server.py on POST /voice/handle.
    """
    knowledge = core.load_chatbot_knowledge(cfg)
    history = _calls.get(call_sid, [])

    if not speech_text:
        return core.twiml_say_hangup(
            "Sorry, I didn't catch that. Please call back. Goodbye."
        )

    history.append({"role": "user", "content": speech_text})

    reply = core.chat_deepseek(
        cfg["deepseek"]["api_key"],
        history[-MAX_TURNS:],
        system_prompt=build_system_prompt(cfg, knowledge),
        max_tokens=120
    )

    history.append({"role": "assistant", "content": reply})
    _calls[call_sid] = history[-MAX_TURNS:]

    base = cfg.get("server", {}).get("public_url", "")

    # End of call?
    if "[END]" in reply or len(history) >= MAX_TURNS * 2:
        clean = reply.replace("[END]", "").strip()
        send_call_summary(cfg, caller_number, history)
        return core.twiml_say_hangup(
            f"{clean} Thank you for calling. Goodbye."
        )

    return core.twiml_gather(reply, f"{base}/voice/handle")


def send_call_summary(cfg, caller_number, history):
    """SMS the owner a summary of the completed call + log it."""
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    data = core.ask_deepseek(
        cfg["deepseek"]["api_key"],
        f"Summarise this phone call for the business owner. Return ONLY JSON "
        f"keys: CallerNeed, ActionRequired.\n\n{convo}",
        max_tokens=120
    ) or {}

    need   = core.safe_text(data.get("CallerNeed"), "General enquiry")
    action = core.safe_text(data.get("ActionRequired"), "Review and call back")

    tw = cfg["twilio"]
    if "YOUR_" not in tw["account_sid"]:
        core.send_sms(tw["account_sid"], tw["auth_token"], tw["from_number"],
                      tw["owner_mobile"],
                      f"AI ANSWERED A CALL from {caller_number}. "
                      f"Need: {need}. Action: {action}")

    core.sheets_append_row(
        cfg["google_sheets"]["sheet_id"],
        cfg["google_sheets"]["tabs"].get("leads", "Lead_Log"),
        [caller_number, caller_number, need, "Voice Call", core.timestamp()]
    )
    log.info(f"Call summary sent for {caller_number}")


def run():
    print("\nModule 24 (Voice Agent) runs via the GAOS web server.")
    print("Start it with:  python gaos_server.py\n")


if __name__ == "__main__":
    run()
