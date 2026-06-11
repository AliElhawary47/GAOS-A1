"""
GAOS™ MODULE 27 — Document Sentinel
Zone 1: React | Standalone: £1,100 | In: Enterprise

Every contract, letter, and PDF that lands in your inbox contains
hidden obligations — deadlines, renewal windows, penalty clauses,
compliance requirements. Someone has to read them. Usually that
someone reads fast and misses something.

Document Sentinel reads every incoming document with a second pass,
using AI to extract what the document REQUIRES of the business owner,
not just what it says. Each obligation becomes a row in a
Sentinel_Actions sheet with the deadline date and source. Urgent
items trigger an immediate alert.

The invisible pain: The deadline buried in paragraph 7 of a contract
that nobody noticed until day 15. The penalty clause that cost £4,000.
The insurance renewal window that closed quietly while everyone was busy.

No new APIs. No new infrastructure. One additional AI prompt on every
document already flowing through GAOS.

Target: Legal, accountancy, property, any business receiving contracts.
"""

import re
from datetime import datetime
import gaos_core as core

log = core.get_logger("document_sentinel")

ACTIONS_TAB   = "Sentinel_Actions"
SENTINEL_MARK = "SENTINEL_CHECKED"

# Claim label: module 01 (Invoice Scanner) watches the same PDF emails,
# so neither module may mark them read — each excludes its own label
# instead, and the email stays unread for the owner.
SENTINEL_LABEL = "GAOS-Sentinel"
SENTINEL_QUERY = "is:unread has:attachment filename:pdf -label:gaos-sentinel"

# Canonical Sentinel_Actions columns (must match gaos_install.TAB_HEADERS)
ACTIONS_HEADERS = [
    "Logged At", "Source Email", "Document Type", "Obligation",
    "Deadline Date", "Priority", "Status"
]

SENTINEL_PROMPT = """You are a legal obligation scanner for a small business.

Read the following document extract and identify EVERY specific obligation,
deadline, renewal window, penalty clause, or compliance requirement it places
on the business.

For each one return a JSON array of objects with these exact keys:
  - obligation: plain English description of what must be done (max 15 words)
  - deadline: date string in YYYY-MM-DD format, or "" if no date given
  - priority: "urgent" if deadline within 14 days or penalty risk, else "normal"

Return ONLY a valid JSON array. No explanation. No markdown.
If there are no obligations, return [].

Document:
{text}"""


def extract_obligations(api_key, text):
    """Sends document text to AI and returns a list of obligations."""
    if not text or len(text.strip()) < 50:
        return []
    prompt = SENTINEL_PROMPT.format(text=text[:3000])   # cap context
    result = core.ask_deepseek(api_key, prompt, max_tokens=500)
    if not result:
        return []
    if isinstance(result, list):
        return result
    # If ask_deepseek returned a dict (single object), wrap it
    if isinstance(result, dict):
        return [result]
    return []


def is_already_checked(snippet):
    """Avoids re-processing emails we've already sentinel-checked."""
    return SENTINEL_MARK in snippet


def process_new_documents(gmail, cfg):
    """
    Watches for new emails with PDF attachments.
    Extracts obligations from each document.
    Logs them to Sentinel_Actions sheet.
    Sends immediate alert for urgent ones.
    """
    sheet_id = cfg["google_sheets"]["sheet_id"]
    api_key  = cfg["deepseek"]["api_key"]

    try:
        results = gmail.users().messages().list(
            userId="me",
            q=SENTINEL_QUERY,
            maxResults=15
        ).execute()
        messages = results.get("messages", [])
    except Exception as e:
        log.error(f"Gmail fetch error: {e}")
        return 0

    processed = 0
    urgent_items = []

    for msg in messages:
        try:
            detail = gmail.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()
            headers   = {h["name"]: h["value"]
                         for h in detail["payload"].get("headers", [])}
            from_addr = headers.get("From", "unknown")
            subject   = headers.get("Subject", "no subject")

            # Extract text from all PDF attachments, recursing into nested
            # MIME containers (HTML emails wrap attachments in multipart/*)
            def _iter_parts(payload):
                yield payload
                for sub in payload.get("parts", []):
                    yield from _iter_parts(sub)

            all_text = ""
            for part in _iter_parts(detail["payload"]):
                filename = part.get("filename", "")
                is_pdf = ("pdf" in part.get("mimeType", "")
                          or filename.lower().endswith(".pdf"))
                if not is_pdf:
                    continue
                att_id = part.get("body", {}).get("attachmentId")
                if not att_id:
                    continue
                att  = gmail.users().messages().attachments().get(
                    userId="me", messageId=msg["id"], id=att_id
                ).execute()
                data = att.get("data", "")
                if data:
                    import base64
                    # "==" pad: Gmail returns unpadded base64url
                    raw  = base64.urlsafe_b64decode(data + "==")
                    all_text += core.extract_pdf_text(raw) + "\n"

            if not all_text.strip():
                # No readable PDF text — mark and skip
                core.gmail_label(gmail, msg["id"], SENTINEL_LABEL)
                continue

            log.info(f"Sentinel scanning: {subject[:50]} from {from_addr[:30]}")

            obligations = extract_obligations(api_key, all_text)
            logged      = 0

            for ob in obligations:
                obligation  = str(ob.get("obligation", "")).strip()
                deadline    = str(ob.get("deadline",   "")).strip()
                priority    = str(ob.get("priority",   "normal")).strip().lower()

                if not obligation:
                    continue

                core.sheets_append_row(sheet_id, ACTIONS_TAB, [
                    core.timestamp(), from_addr, subject, obligation,
                    deadline, priority, "Open"
                ])
                logged += 1

                if priority == "urgent":
                    urgent_items.append({
                        "from":       from_addr,
                        "subject":    subject,
                        "obligation": obligation,
                        "deadline":   deadline,
                    })

            log.info(f"  → {logged} obligation(s) logged "
                     f"({sum(1 for o in obligations if o.get('priority')=='urgent')} urgent)")

            # Claim with our label so we don't re-process — never mark
            # read: module 01 still needs the unread email, and the
            # owner should still see it in their inbox.
            core.gmail_label(gmail, msg["id"], SENTINEL_LABEL)
            processed += 1

        except Exception as e:
            log.error(f"Error processing message {msg['id']}: {e}")
            continue

    # Alert on urgent items
    if urgent_items:
        _send_urgent_alert(gmail, cfg, urgent_items)

    return processed


def _send_urgent_alert(gmail, cfg, items):
    """Emails an immediate alert for urgent obligations found."""
    lines = [
        "URGENT: GAOS Document Sentinel has found time-sensitive obligations.",
        f"Found in {len(items)} document(s) — action required:\n",
    ]
    for item in items:
        lines.append(f"From:       {item['from']}")
        lines.append(f"Document:   {item['subject']}")
        lines.append(f"Obligation: {item['obligation']}")
        if item["deadline"]:
            lines.append(f"Deadline:   {item['deadline']}")
        lines.append("")

    lines.append("All obligations logged to your Sentinel_Actions sheet.")
    lines.append("\nAether Frameworks — GAOS™ Document Sentinel")

    core.gmail_send(
        gmail,
        cfg["gmail"]["alert_email"],
        cfg["gmail"]["watch_inbox"],
        f"URGENT — Document Sentinel: {len(items)} obligation(s) need attention",
        "\n".join(lines)
    )
    log.info(f"Urgent alert sent for {len(items)} obligation(s)")


def ensure_actions_tab(cfg):
    """Creates the Sentinel_Actions tab if it doesn't exist."""
    core.sheets_find_or_create_tab(cfg["google_sheets"]["sheet_id"],
                                   ACTIONS_TAB, ACTIONS_HEADERS)


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    ensure_actions_tab(cfg)
    log.info("module_27_document_sentinel: Watching for incoming documents.")
    core.run_loop(lambda: process_new_documents(gmail, cfg),
                  cfg.get("settings", {}).get("check_every_seconds", 300))


if __name__ == "__main__":
    run()
