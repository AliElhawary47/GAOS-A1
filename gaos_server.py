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

import base64
import hashlib
import hmac
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

MAX_MESSAGE_CHARS = 2000   # clamp inbound chat/WhatsApp messages (token-burn guard)


def _load():
    global cfg
    cfg = core.load_config()
    source = core.config_source()
    if cfg:
        log.info("Config loaded (source: %s).", source)
    else:
        log.error(
            "Config NOT loaded (source: %s) — set GAOS_CONFIG_JSON in your "
            "deployment environment or place config.json in the project root. "
            "Conversational endpoints will fail until config is available.",
            source,
        )

_load()


def _get_cfg() -> dict:
    """Returns config, retrying the load if it was empty at boot.

    Self-heals the case where env vars were added to the platform after
    the process started, or a config file appeared on disk.
    """
    global cfg
    if not cfg:
        _load()
    return cfg


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


# ── Security: Twilio webhook signature validation (opt-in) ───────
#
# Without this, anyone who discovers the server URL can POST to /whatsapp
# and /voice — burning AI tokens and SMS-spamming the owner.
# Enable by setting GAOS_VALIDATE_TWILIO=1 in the deployment environment
# (requires twilio.auth_token in config). Implements Twilio's documented
# HMAC-SHA1 scheme with no extra dependency.

def _twilio_request_is_valid() -> bool:
    if os.environ.get("GAOS_VALIDATE_TWILIO") != "1":
        return True  # validation disabled (default) — backward compatible
    auth_token = core.safe_text(
        _get_cfg().get("twilio", {}).get("auth_token")
    ) or os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        log.warning("GAOS_VALIDATE_TWILIO=1 but no twilio auth_token available")
        return True  # fail open rather than silently dropping real customers
    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        return False
    # Twilio spec: full URL + form params sorted by key, values appended
    url = request.url
    payload = url + "".join(
        k + request.form[k] for k in sorted(request.form.keys())
    )
    digest = hmac.new(
        auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


# ── CORS: the chatbot widget runs on CLIENT websites ─────────────
#
# widget.js is embedded on customers' own domains and fetch()es /chat
# cross-origin with a JSON content type — which triggers a browser
# preflight. Without these headers every embedded chatbot request is
# blocked by the browser. Restrict origins via the GAOS_ALLOWED_ORIGINS
# env var (comma-separated) or cfg["server"]["allowed_origins"];
# default "*" so the widget works out of the box.

def _allowed_origin() -> str:
    configured = (
        os.environ.get("GAOS_ALLOWED_ORIGINS")
        or ",".join(_get_cfg().get("server", {}).get("allowed_origins", []))
        or "*"
    )
    if configured == "*":
        return "*"
    origin = request.headers.get("Origin", "")
    allowed = {o.strip() for o in configured.split(",") if o.strip()}
    return origin if origin in allowed else ""


@app.after_request
def _add_cors_headers(response):
    if request.path in ("/chat", "/health"):
        origin = _allowed_origin()
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Max-Age"] = "86400"
            if origin != "*":
                response.headers["Vary"] = "Origin"
    return response


@app.route("/chat", methods=["OPTIONS"])
def chat_preflight():
    """Browser CORS preflight for the embedded widget."""
    return ("", 204)

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
    current = _get_cfg()
    return jsonify({
        "status": "ok",
        "modules": {
            "chatbot":   _chatbot()  is not None,
            "whatsapp":  _whatsapp() is not None,
            "voice":     _voice()    is not None,
        },
        "config_loaded": bool(current),
        "config_source": core.config_source(),
        "gmail_connected": gmail is not None,  # lazy — None until first use
    })


@app.route("/chat", methods=["POST"])
def chat():
    """Website chatbot endpoint. Called by widget.js."""
    try:
        data       = request.get_json(force=True) or {}
        session_id = str(data.get("session_id", "default"))[:128]
        message    = str(data.get("message", "")).strip()[:MAX_MESSAGE_CHARS]

        if not message:
            return jsonify({"error": "message is required"}), 400

        current = _get_cfg()
        if not current:
            log.error("/chat called but no config is loaded")
            return jsonify({"reply": "Chatbot is being set up. Please try again later."}), 503

        m = _chatbot()
        if m is None:
            return jsonify({"reply": "Chatbot is unavailable. Please try again later."}), 503

        reply = m.handle_message(current, session_id, message)
        return jsonify({"reply": reply})
    except Exception as e:
        log.error(f"/chat error: {e}")
        return jsonify({"reply": "Something went wrong. Please try again."}), 500


@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    """Twilio WhatsApp webhook — receives incoming WhatsApp messages."""
    try:
        if not _twilio_request_is_valid():
            log.warning("/whatsapp rejected: invalid Twilio signature from %s",
                        request.remote_addr)
            return Response("Forbidden", status=403)

        body   = request.form.get("Body", "").strip()[:MAX_MESSAGE_CHARS]
        sender = request.form.get("From", "").strip()

        if not body or not sender:
            return Response(_twiml_empty_message(), mimetype="text/xml")

        current = _get_cfg()
        m = _whatsapp()
        if m is None or not current:
            return Response(
                _twiml_message("Our AI assistant is temporarily unavailable."),
                mimetype="text/xml"
            )

        reply = m.handle_message(current, sender, body)
        return Response(_twiml_message(reply), mimetype="text/xml")
    except Exception as e:
        log.error(f"/whatsapp error: {e}")
        return Response(_twiml_message("Something went wrong. Please try again."), mimetype="text/xml")


@app.route("/voice", methods=["POST"])
def voice():
    """Twilio Voice webhook — answers an inbound call with a greeting."""
    try:
        if not _twilio_request_is_valid():
            log.warning("/voice rejected: invalid Twilio signature from %s",
                        request.remote_addr)
            return Response("Forbidden", status=403)

        call_sid = request.form.get("CallSid", "unknown")
        current  = _get_cfg()
        m = _voice()
        if m is None or not current:
            return Response(
                core.twiml_say_hangup("Thank you for calling. Please try again shortly."),
                mimetype="text/xml"
            )
        twiml = m.greeting(current, call_sid)
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
        if not _twilio_request_is_valid():
            log.warning("/voice/handle rejected: invalid Twilio signature from %s",
                        request.remote_addr)
            return Response("Forbidden", status=403)

        call_sid     = request.form.get("CallSid", "unknown")
        caller       = request.form.get("From", "unknown")
        speech_text  = request.form.get("SpeechResult", "").strip()[:MAX_MESSAGE_CHARS]

        current = _get_cfg()
        m = _voice()
        if m is None or not current:
            return Response(
                core.twiml_say_hangup("Sorry, something went wrong. Please call back."),
                mimetype="text/xml"
            )
        twiml = m.handle_turn(current, call_sid, caller, speech_text)
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
    # Railway/Heroku inject the port via the PORT env var; config is the
    # local-dev fallback.
    port = int(os.environ.get("PORT",
               _get_cfg().get("server", {}).get("port", 8080)))
    log.info(f"GAOS™ Web Server starting on port {port}")
    log.info("Routes: /health  /chat  /whatsapp  /voice  /voice/handle  /widget.js")
    app.run(host="0.0.0.0", port=port, debug=False)
