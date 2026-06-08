"""
GAOS™ Web Server
Serves the three conversational modules (22, 23, 24) via Flask.

Routes:
  GET  /health          — uptime check (used by Railway)
  POST /chat            — website chatbot (Module 22)
  POST /whatsapp        — Twilio WhatsApp webhook (Module 23)
  POST /voice           — Twilio Voice: initial call greeting (Module 24)
  POST /voice/handle    — Twilio Voice: each spoken turn (Module 24)
  GET  /widget.js       — embeddable chatbot JS widget

Run locally:   python gaos_server.py
Production:    gunicorn gaos_server:app  (or :application)
"""

import os
import logging
from flask import Flask, request, jsonify, Response, send_from_directory

import gaos_core as core

app = Flask(__name__)
application = app  # gunicorn alias

logging.basicConfig(
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("gaos.server")

# ── Startup ──────────────────────────────────────────────────────

cfg  = {}
gmail = None

def _load():
    global cfg
    try:
        cfg = core.load_config()
        log.info("Config loaded.")
    except Exception as e:
        log.error(f"Config load failed: {e}")
        cfg = {}

_load()

def _get_gmail():
    """Lazy Gmail connection — only connects on first route that needs it."""
    global gmail
    if gmail is None:
        try:
            gmail = core.connect_gmail()
            if gmail:
                log.info("Gmail connected.")
        except Exception as e:
            log.warning(f"Gmail connect failed: {e}")
    return gmail

# ── Lazy module imports ───────────────────────────────────────────

_m22 = _m23 = _m24 = None

def _chatbot():
    global _m22
    if _m22 is None:
        try:
            from modules import module_22_website_chatbot as m
            _m22 = m
        except ImportError as e:
            log.error(f"Module 22 import failed: {e}")
    return _m22

def _whatsapp():
    global _m23
    if _m23 is None:
        try:
            from modules import module_23_whatsapp_agent as m
            _m23 = m
        except ImportError as e:
            log.error(f"Module 23 import failed: {e}")
    return _m23

def _voice():
    global _m24
    if _m24 is None:
        try:
            from modules import module_24_voice_agent as m
            _m24 = m
        except ImportError as e:
            log.error(f"Module 24 import failed: {e}")
    return _m24

# ── Routes ───────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "modules": {
            "chatbot":   _chatbot()  is not None,
            "whatsapp":  _whatsapp() is not None,
            "voice":     _voice()    is not None,
        },
        "config_loaded": bool(cfg),
        "gmail_connected": gmail is not None,  # lazy — None until first use
    })


@app.route("/chat", methods=["POST"])
def chat():
    """Website chatbot endpoint. Called by widget.js."""
    try:
        data       = request.get_json(force=True) or {}
        session_id = str(data.get("session_id", "default"))
        message    = str(data.get("message", "")).strip()

        if not message:
            return jsonify({"error": "message is required"}), 400

        m = _chatbot()
        if m is None:
            return jsonify({"reply": "Chatbot is unavailable. Please try again later."}), 503

        reply = m.handle_message(cfg, session_id, message)
        return jsonify({"reply": reply})
    except Exception as e:
        log.error(f"/chat error: {e}")
        return jsonify({"reply": "Something went wrong. Please try again."}), 500


@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    """Twilio WhatsApp webhook — receives incoming WhatsApp messages."""
    try:
        body   = request.form.get("Body", "").strip()
        sender = request.form.get("From", "").strip()

        if not body or not sender:
            return Response(_twiml_empty_message(), mimetype="text/xml")

        m = _whatsapp()
        if m is None:
            return Response(
                _twiml_message("Our AI assistant is temporarily unavailable."),
                mimetype="text/xml"
            )

        reply = m.handle_message(cfg, sender, body)
        return Response(_twiml_message(reply), mimetype="text/xml")
    except Exception as e:
        log.error(f"/whatsapp error: {e}")
        return Response(_twiml_message("Something went wrong. Please try again."), mimetype="text/xml")


@app.route("/voice", methods=["POST"])
def voice():
    """Twilio Voice webhook — answers an inbound call with a greeting."""
    try:
        call_sid = request.form.get("CallSid", "unknown")
        m = _voice()
        if m is None:
            return Response(
                core.twiml_say_hangup("Thank you for calling. Please try again shortly."),
                mimetype="text/xml"
            )
        twiml = m.greeting(cfg, call_sid)
        return Response(twiml, mimetype="text/xml")
    except Exception as e:
        log.error(f"/voice error: {e}")
        return Response(
            core.twiml_say_hangup("We are experiencing technical difficulties. Please call back."),
            mimetype="text/xml"
        )


@app.route("/voice/handle", methods=["POST"])
def voice_handle():
    """Twilio Voice gather callback — processes each spoken turn."""
    try:
        call_sid     = request.form.get("CallSid", "unknown")
        caller       = request.form.get("From", "unknown")
        speech_text  = request.form.get("SpeechResult", "").strip()

        m = _voice()
        if m is None:
            return Response(
                core.twiml_say_hangup("Sorry, something went wrong. Please call back."),
                mimetype="text/xml"
            )
        twiml = m.handle_turn(cfg, call_sid, caller, speech_text)
        return Response(twiml, mimetype="text/xml")
    except Exception as e:
        log.error(f"/voice/handle error: {e}")
        return Response(
            core.twiml_say_hangup("Sorry, I lost the connection. Please call back."),
            mimetype="text/xml"
        )


@app.route("/widget.js", methods=["GET"])
def widget_js():
    """Serves the embeddable chatbot widget."""
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    return send_from_directory(static_dir, "widget.js", mimetype="application/javascript")


# ── TwiML helpers ────────────────────────────────────────────────

def _twiml_message(text: str) -> str:
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe}</Message></Response>'

def _twiml_empty_message() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


# ── Entry point ──────────────────────────────────────────────────

if __name__ == "__main__":
    port = cfg.get("server", {}).get("port", 8080)
    log.info(f"GAOS™ Web Server starting on port {port}")
    log.info("Routes: /health  /chat  /whatsapp  /voice  /voice/handle  /widget.js")
    app.run(host="0.0.0.0", port=port, debug=False)
