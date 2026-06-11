"""
GAOS™ Shared Runtime Library  v3.2
====================================
Centralised helpers used by all 33+ GAOS modules via ``import gaos_core as core``.

Required credential files (place in the project root):
  credentials.json   — Google OAuth2 client secrets (Desktop app type).
                        Download from Google Cloud Console → APIs & Services
                        → Credentials.  Needed by connect_gmail().
  token.json         — Auto-generated on first OAuth run; refreshed automatically.
                        Delete this file to force a fresh browser login.
  service_account.json — Google service-account key (JSON format) with Sheets
                          Editor access granted on each target spreadsheet.
                          Used by the Sheets helpers.  If absent the Sheets
                          helpers fall back to the same OAuth token.json used
                          by Gmail.
"""

import base64
import io
import json
import logging
import os
import re
import time
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

import requests
# Heavy/optional deps are imported lazily inside the functions that use them:
#   pdfplumber      → extract_pdf_text()
#   gspread         → _get_sheets_client()
#   google-auth-*   → connect_gmail(), _get_sheets_client()

_GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]

_log = logging.getLogger("gaos.core")
logging.basicConfig(
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
    level=logging.INFO,
)

_sheets_client = None


def load_config(path="config.json") -> dict:
    """Loads config.json from disk; falls back to the GAOS_CONFIG_JSON env var.

    Cloud deployment (Railway/Oracle): config.json is gitignored and never
    present on the server.  Paste the full JSON into a single environment
    variable named GAOS_CONFIG_JSON instead — it is parsed identically.
    Local development: the file always wins when it exists.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        pass  # normal in cloud deploys — fall through to env var
    except Exception as exc:
        _log.error("load_config: %s is unreadable: %s", path, exc)

    env_json = os.environ.get("GAOS_CONFIG_JSON", "").strip()
    if env_json:
        try:
            return json.loads(env_json)
        except Exception as exc:
            _log.error("load_config: GAOS_CONFIG_JSON is not valid JSON: %s", exc)
            return {}

    _log.error(
        "load_config: no config found — create config.json or set GAOS_CONFIG_JSON"
    )
    return {}


def config_source() -> str:
    """Reports where config is coming from: 'file', 'env', or 'none'."""
    if os.path.exists("config.json"):
        return "file"
    if os.environ.get("GAOS_CONFIG_JSON", "").strip():
        return "env"
    return "none"


def get_secret(key_path: str, default=None):
    """Dot-path lookup into config.json.
    e.g. get_secret('deepseek.api_key') → cfg['deepseek']['api_key']
    Falls back to env vars: DEEPSEEK_API_KEY for 'deepseek.api_key'.
    """
    # Try environment variable first (KEY_PATH → SCREAMING_SNAKE)
    env_key = key_path.replace(".", "_").upper()
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val
    cfg = load_config()
    parts = key_path.split(".")
    node = cfg
    try:
        for part in parts:
            node = node[part]
        return node
    except (KeyError, TypeError):
        return default


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"gaos.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(name)s  %(levelname)s  %(message)s")
        )
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def connect_gmail():
    """Connects to Gmail.

    Credential resolution order:
      1. token.json on disk (local dev — written by the first OAuth run)
      2. GAOS_TOKEN_JSON env var (cloud deploys — paste token.json contents)
      3. Interactive browser OAuth via credentials.json — LOCAL ONLY.
         Never attempted when GAOS_HEADLESS=1 or when running without a
         token, so a gunicorn worker can never hang waiting for a browser.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", _GMAIL_SCOPES)
        else:
            env_token = os.environ.get("GAOS_TOKEN_JSON", "").strip()
            if env_token:
                creds = Credentials.from_authorized_user_info(
                    json.loads(env_token), _GMAIL_SCOPES
                )

        if creds and not creds.valid and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            try:  # persist the refreshed token for this process's lifetime
                with open("token.json", "w", encoding="utf-8") as token_file:
                    token_file.write(creds.to_json())
            except OSError:
                pass  # read-only filesystem — refreshed creds still work in memory

        if creds and creds.valid:
            return build("gmail", "v1", credentials=creds)

        # No usable token — interactive flow is a local-dev-only path.
        if os.environ.get("GAOS_HEADLESS") == "1":
            _log.error(
                "connect_gmail: no valid token and GAOS_HEADLESS=1 — "
                "set GAOS_TOKEN_JSON (contents of a locally generated token.json)"
            )
            return None
        if not os.path.exists("credentials.json"):
            _log.error(
                "connect_gmail: no token.json/GAOS_TOKEN_JSON and no "
                "credentials.json — Gmail features disabled"
            )
            return None

        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json", _GMAIL_SCOPES
        )
        creds = flow.run_local_server(port=0)
        with open("token.json", "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())
        return build("gmail", "v1", credentials=creds)
    except Exception as exc:
        _log.error("connect_gmail failed: %s", exc)
        return None


def gmail_send(gmail, to: str, from_addr: str, subject: str, body: str):
    try:
        msg = MIMEText(body)
        msg["to"] = to
        msg["from"] = from_addr
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        gmail.users().messages().send(userId="me", body={"raw": raw}).execute()
    except Exception as exc:
        _log.error("gmail_send failed: %s", exc)


def gmail_search(gmail, query: str, max_results: int = 25) -> list:
    try:
        result = (
            gmail.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        return result.get("messages", [])
    except Exception as exc:
        _log.error("gmail_search failed: %s", exc)
        return []


def gmail_get_message(gmail, message_id: str):
    try:
        msg = (
            gmail.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        headers_list = msg.get("payload", {}).get("headers", [])
        headers_dict = {h["name"]: h["value"] for h in headers_list}
        body_text = gmail_get_body_text(msg)
        return headers_dict, body_text
    except Exception as exc:
        _log.error("gmail_get_message failed: %s", exc)
        return {}, ""


def gmail_get_body_text(msg: dict) -> str:
    try:
        def _extract(payload):
            mime = payload.get("mimeType", "")
            if mime == "text/plain":
                data = payload.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data + "==").decode(
                        "utf-8", errors="replace"
                    )
            parts = payload.get("parts", [])
            for part in parts:
                result = _extract(part)
                if result:
                    return result
            return ""

        return _extract(msg.get("payload", {}))
    except Exception as exc:
        _log.error("gmail_get_body_text failed: %s", exc)
        return ""


def gmail_download_pdf(gmail, message_id: str):
    try:
        msg = (
            gmail.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

        def _iter_parts(payload):
            yield payload
            for part in payload.get("parts", []):
                yield from _iter_parts(part)

        for part in _iter_parts(msg.get("payload", {})):
            mime = part.get("mimeType", "")
            filename = part.get("filename", "")
            is_pdf = mime == "application/pdf" or (
                filename and filename.lower().endswith(".pdf")
            )
            if not is_pdf:
                continue
            attachment_id = part.get("body", {}).get("attachmentId")
            if not attachment_id:
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data + "=="), filename or "attachment.pdf"
                continue
            att = (
                gmail.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )
            pdf_bytes = base64.urlsafe_b64decode(att["data"] + "==")
            return pdf_bytes, filename or "attachment.pdf"
        return None, None
    except Exception as exc:
        _log.error("gmail_download_pdf failed: %s", exc)
        return None, None


def gmail_create_draft(gmail, to: str, subject: str, body: str):
    try:
        profile = gmail.users().getProfile(userId="me").execute()
        from_addr = profile.get("emailAddress", "me")
        msg = MIMEText(body)
        msg["to"] = to
        msg["from"] = from_addr
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        gmail.users().drafts().create(
            userId="me", body={"message": {"raw": raw}}
        ).execute()
    except Exception as exc:
        _log.error("gmail_create_draft failed: %s", exc)


def gmail_mark_read(gmail, message_id: str):
    try:
        gmail.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()
    except Exception as exc:
        _log.error("gmail_mark_read failed: %s", exc)


def gmail_label(gmail, message_id: str, label_name: str):
    try:
        existing = gmail.users().labels().list(userId="me").execute().get("labels", [])
        label_id = None
        for lbl in existing:
            if lbl["name"].lower() == label_name.lower():
                label_id = lbl["id"]
                break
        if not label_id:
            created = gmail.users().labels().create(
                userId="me", body={"name": label_name}
            ).execute()
            label_id = created["id"]
        gmail.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label_id]},
        ).execute()
    except Exception as exc:
        _log.error("gmail_label failed: %s", exc)


def ask_deepseek(
    api_key: str,
    prompt: str,
    max_tokens: int = 500,
    expect_json: bool = True,
    system: str = None,
):
    """Routes through gaos_ai (DeepSeek primary → Groq fallback).
    api_key accepted for backward compat but provider keys come from config/env.
    """
    try:
        import gaos_ai
        return gaos_ai.ask_ai(prompt, api_key=api_key, max_tokens=max_tokens,
                               expect_json=expect_json, system=system)
    except ImportError:
        pass
    # Bare fallback when gaos_ai is unavailable
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": "deepseek-chat", "messages": messages,
               "max_tokens": max_tokens, "temperature": 0.2}
    if expect_json:
        payload["response_format"] = {"type": "json_object"}
    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            if not expect_json:
                return content
            cleaned = re.sub(r"^```(?:json)?\s*", "", content.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            return json.loads(cleaned)
        except Exception as exc:
            _log.error("ask_deepseek attempt %d failed: %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(2 ** attempt)
    return {} if expect_json else ""


def chat_deepseek(
    api_key: str,
    messages: list,
    system_prompt: str = None,
    max_tokens: int = 500,
) -> str:
    """Routes through gaos_ai (DeepSeek primary → Groq fallback)."""
    try:
        import gaos_ai
        return gaos_ai.chat_ai(messages, api_key=api_key,
                                system_prompt=system_prompt, max_tokens=max_tokens)
    except ImportError:
        pass
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)
    payload = {"model": "deepseek-chat", "messages": full_messages,
               "max_tokens": max_tokens, "temperature": 0.4}
    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            _log.error("chat_deepseek attempt %d failed: %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(2 ** attempt)
    return ""


def _get_sheets_client():
    global _sheets_client
    if _sheets_client is not None:
        return _sheets_client
    try:
        import gspread
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
        from google.oauth2.credentials import Credentials

        _SHEETS_SCOPES = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        if os.path.exists("service_account.json"):
            creds = service_account.Credentials.from_service_account_file(
                "service_account.json", scopes=_SHEETS_SCOPES
            )
            _sheets_client = gspread.authorize(creds)
            return _sheets_client
        env_sa = os.environ.get("GAOS_SERVICE_ACCOUNT_JSON", "").strip()
        if env_sa:
            creds = service_account.Credentials.from_service_account_info(
                json.loads(env_sa), scopes=_SHEETS_SCOPES
            )
            _sheets_client = gspread.authorize(creds)
            return _sheets_client
        oauth_info = None
        if os.path.exists("token.json"):
            oauth_creds = Credentials.from_authorized_user_file(
                "token.json", scopes=_SHEETS_SCOPES
            )
        else:
            env_token = os.environ.get("GAOS_TOKEN_JSON", "").strip()
            oauth_info = json.loads(env_token) if env_token else None
            oauth_creds = (
                Credentials.from_authorized_user_info(oauth_info, scopes=_SHEETS_SCOPES)
                if oauth_info else None
            )
        if oauth_creds:
            if oauth_creds.expired and oauth_creds.refresh_token:
                oauth_creds.refresh(Request())
            _sheets_client = gspread.authorize(oauth_creds)
            return _sheets_client
        _log.error(
            "_get_sheets_client: no service_account.json, token.json, "
            "GAOS_SERVICE_ACCOUNT_JSON, or GAOS_TOKEN_JSON found"
        )
        return None
    except Exception as exc:
        _log.error("_get_sheets_client failed: %s", exc)
        return None


def sheets_read_all(sheet_id: str, tab_name: str) -> list:
    try:
        gc = _get_sheets_client()
        ws = gc.open_by_key(sheet_id).worksheet(tab_name)
        return ws.get_all_records(default_blank="")
    except Exception as exc:
        _log.error("sheets_read_all failed: %s", exc)
        return []


def sheets_append_row(sheet_id: str, tab_name: str, row_values: list):
    try:
        gc = _get_sheets_client()
        ws = gc.open_by_key(sheet_id).worksheet(tab_name)
        ws.append_row(row_values, value_input_option="USER_ENTERED")
    except Exception as exc:
        _log.error("sheets_append_row failed: %s", exc)


def sheets_update_cell(sheet_id: str, tab_name: str, row_index: int, col, value: str):
    try:
        gc = _get_sheets_client()
        ws = gc.open_by_key(sheet_id).worksheet(tab_name)
        if isinstance(col, str):
            headers = ws.row_values(1)
            col_idx = headers.index(col) + 1
        else:
            col_idx = col
        ws.update_cell(row_index, col_idx, value)
    except Exception as exc:
        _log.error("sheets_update_cell failed: %s", exc)


def send_sms(
    account_sid: str,
    auth_token: str,
    from_number: str,
    to_number: str,
    body: str,
):
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        requests.post(
            url,
            auth=(account_sid, auth_token),
            data={"From": from_number, "To": to_number, "Body": body},
            timeout=30,
        ).raise_for_status()
    except Exception as exc:
        _log.error("send_sms failed: %s", exc)


def send_whatsapp(
    account_sid: str,
    auth_token: str,
    from_number: str,
    to_number: str,
    body: str,
):
    try:
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"
        body = body[:1600]
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        requests.post(
            url,
            auth=(account_sid, auth_token),
            data={"From": from_number, "To": to_number, "Body": body},
            timeout=30,
        ).raise_for_status()
    except Exception as exc:
        _log.error("send_whatsapp failed: %s", exc)


def post_to_slack(webhook_url: str, message: str):
    try:
        requests.post(
            webhook_url,
            json={"text": message},
            timeout=15,
        ).raise_for_status()
    except Exception as exc:
        _log.error("post_to_slack failed: %s", exc)


def extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n".join(pages)
    except Exception as exc:
        _log.error("extract_pdf_text failed: %s", exc)
        return ""


def archive_file(archive_folder: str, content: bytes, filename: str):
    try:
        folder = Path(archive_folder)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / filename
        if target.exists():
            stem = target.stem
            suffix = target.suffix
            counter = 1
            while target.exists():
                target = folder / f"{stem}_{counter}{suffix}"
                counter += 1
        target.write_bytes(content)
    except Exception as exc:
        _log.error("archive_file failed: %s", exc)


def safe_text(value, default: str = "") -> str:
    try:
        if value is None or value == "":
            return default
        return str(value).strip() or default
    except Exception:
        return default


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def twiml_gather(prompt_text: str, action_url: str) -> str:
    safe_prompt = prompt_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_url = action_url.replace("&", "&amp;")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Gather input="speech" speechTimeout="auto" language="en-GB" action="{safe_url}">'
        f'<Say voice="Polly.Amy">{safe_prompt}</Say>'
        "</Gather>"
        "</Response>"
    )


def twiml_say_hangup(text: str) -> str:
    safe_t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Say voice="Polly.Amy">{safe_t}</Say>'
        "<Hangup/>"
        "</Response>"
    )


# ── SCHEDULING ───────────────────────────────────────────────────

# Dedupe registry: remembers which (slot, date) combinations already fired
# this process lifetime, so a daily job can never double-send within one
# window (e.g. two polls both landing inside an 08:00–08:05 window).
_fired_slots: set = set()


def should_run_at(hour: int, weekday: int = None, day_of_month: int = None,
                  minute_start: int = 0, minute_window: int = 5) -> bool:
    """
    Returns True at most ONCE per scheduled window per day (process-local).

    hour          — 0-23, required
    weekday       — 0=Monday … 6=Sunday (None = every day)
    day_of_month  — 1-31 (None = every day; combined with weekday for e.g. 'first Monday')
    minute_start  — minute the window opens (default 0)
    minute_window — how many minutes the window stays open (default 5)

    Examples:
        should_run_at(8)                        → daily at 08:00–08:05
        should_run_at(8, weekday=0)             → every Monday at 08:00–08:05
        should_run_at(9, day_of_month=1)        → 1st of every month at 09:00–09:05
        should_run_at(7, minute_start=30)       → daily at 07:30–07:35
        should_run_at(7, weekday=0, minute_start=45) → every Monday at 07:45–07:50

    Reliability notes:
      * Double-fire protection — once a slot returns True it cannot return
        True again on the same calendar day, even if a second poll lands
        inside the same window.
      * Set minute_window to at least (poll_seconds / 60) + 1 so polling
        drift cannot skip a window entirely.
    """
    now = datetime.now()
    if now.hour != hour:
        return False
    if not (minute_start <= now.minute < minute_start + minute_window):
        return False
    if weekday is not None and now.weekday() != weekday:
        return False
    if day_of_month is not None and now.day != day_of_month:
        return False

    # Dedupe per CALL SITE per day: two different modules (or two different
    # lines in one module) scheduled at the same hour must never block each
    # other, but the same line polled twice inside one window must not fire twice.
    import sys as _sys
    frame = _sys._getframe(1)
    call_site = (frame.f_code.co_filename, frame.f_lineno)
    slot_key = (call_site, hour, weekday, day_of_month, minute_start,
                now.date().isoformat())
    if slot_key in _fired_slots:
        return False
    # prune entries from previous days so the set never grows unbounded
    today = now.date().isoformat()
    stale = {k for k in _fired_slots if k[5] != today}
    _fired_slots.difference_update(stale)
    _fired_slots.add(slot_key)
    return True


def run_loop(action_fn, poll_seconds: int = 300):
    """
    Standard GAOS polling loop. Calls action_fn() every poll_seconds.
    Handles KeyboardInterrupt for clean Ctrl+C shutdown.
    All exceptions inside action_fn are caught and logged so the loop never dies.

    Usage in a module's run():
        core.run_loop(lambda: check_something(gmail, cfg),
                      cfg["settings"]["check_every_seconds"])
    """
    try:
        while True:
            try:
                action_fn()
            except Exception as exc:
                _log.error("run_loop error: %s", exc)
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print("\nStopped.\n")


# ── CHATBOT KNOWLEDGE ─────────────────────────────────────────────

def load_chatbot_knowledge(cfg: dict) -> str:
    """
    Loads the shared chatbot/voice knowledge base from Google Sheets.
    Returns a formatted string of Q&A pairs used by modules 22, 23, and 24.
    """
    try:
        rows = sheets_read_all(
            cfg["google_sheets"]["sheet_id"],
            cfg["google_sheets"]["tabs"].get("chatbot", "Chatbot_Knowledge")
        )
        pairs = [
            f"Q: {str(r.get('Question', '')).strip()}\nA: {str(r.get('Answer', '')).strip()}"
            for r in rows
            if r.get("Question") and r.get("Answer")
        ]
        return "\n\n".join(pairs)
    except Exception as exc:
        _log.error("load_chatbot_knowledge failed: %s", exc)
        return ""


# ── AUDIT & USAGE LOGGING ─────────────────────────────────────────

def log_action(cfg: dict, module: str, action: str, status: str = "ok",
               detail: str = "") -> None:
    """Appends one row to the Actions_Log sheet tab.
    Called by any module after completing a significant action."""
    try:
        sheet_id = cfg["google_sheets"]["sheet_id"]
        tab      = cfg["google_sheets"]["tabs"].get("actions_log", "Actions_Log")
        sheets_append_row(sheet_id, tab,
                          [timestamp(), module, action, status, detail[:250]])
    except Exception as exc:
        _log.warning("log_action failed: %s", exc)


def log_usage(cfg: dict, module: str, tokens: int, cost_gbp: float = 0.0) -> None:
    """Appends one row to the Usage_Log sheet tab.
    Called automatically by gaos_ai on every AI call."""
    try:
        sheet_id = cfg["google_sheets"]["sheet_id"]
        tab      = cfg["google_sheets"]["tabs"].get("usage_log", "Usage_Log")
        sheets_append_row(sheet_id, tab,
                          [timestamp(), module, tokens, round(cost_gbp, 6)])
    except Exception as exc:
        _log.warning("log_usage failed: %s", exc)


# ── SHEET UTILITIES ───────────────────────────────────────────────

def sheets_find_or_create_tab(sheet_id: str, tab_name: str,
                               headers: list = None) -> None:
    """Ensures a sheet tab exists.  Creates it with optional header row if missing.
    Safe to call on every startup — does nothing when tab already exists."""
    try:
        gc = _get_sheets_client()
        ss = gc.open_by_key(sheet_id)
        existing = [ws.title for ws in ss.worksheets()]
        if tab_name not in existing:
            ws = ss.add_worksheet(title=tab_name, rows=200, cols=20)
            if headers:
                ws.append_row(headers)
            _log.info("Created sheet tab: %s", tab_name)
    except Exception as exc:
        _log.warning("sheets_find_or_create_tab failed for %s: %s", tab_name, exc)


# ── SYSTEM STATS ──────────────────────────────────────────────────

def get_memory_usage_mb() -> float:
    """Returns current process RSS memory in MB.  Requires psutil."""
    try:
        import psutil, os as _os
        return psutil.Process(_os.getpid()).memory_info().rss / 1_048_576
    except Exception:
        return 0.0


def get_system_stats() -> dict:
    """Returns a snapshot of system resource usage for the dashboard."""
    stats: dict = {"memory_mb": round(get_memory_usage_mb(), 1)}
    try:
        import psutil
        stats["disk_usage_percent"] = psutil.disk_usage(".").percent
        stats["cpu_percent"]        = psutil.cpu_percent(interval=0.1)
    except Exception:
        pass
    return stats
