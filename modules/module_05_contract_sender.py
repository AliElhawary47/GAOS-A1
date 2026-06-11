"""
╔══════════════════════════════════════════════════════════════╗
║   GAOS™ MODULE 05 — Automated Contract & Onboarding         ║
║   Standalone: £1,100  |  In: GAOS™ Pro, Enterprise          ║
╠══════════════════════════════════════════════════════════════╣
║   New client details arrive (form email) → GAOS™ fills a    ║
║   contract template → emails it to the client → logs the    ║
║   client to a sheet → alerts the owner that it's sent.      ║
║                                                             ║
║   Target client:  Agencies, recruiters, estate agents       ║
║   Pain solved:    Manual paperwork when onboarding clients   ║
╚══════════════════════════════════════════════════════════════╝

This module fills a plain-text contract template stored in
contract_template.txt. Use {ClientName}, {CompanyName},
{ServiceDescription}, {Fee}, {Date} as placeholders.
"""

import os
import gaos_core as core

log = core.get_logger("contract_sender")


CONTRACT_TEMPLATE_FILE = "contract_template.txt"

DEFAULT_TEMPLATE = """SERVICE AGREEMENT

Date: {Date}

Between: {CompanyName}
And:     {ClientName}

1. SERVICE
{CompanyName} agrees to provide the following service:
{ServiceDescription}

2. FEE
The agreed fee for this service is {Fee}.

3. TERMS
Payment terms and delivery to be confirmed in writing.
This agreement is governed by the laws of England and Wales.

Signed: ______________________   Date: ____________

{CompanyName}
"""


def get_template():
    """Loads the contract template, creating a default if missing."""
    if not os.path.exists(CONTRACT_TEMPLATE_FILE):
        with open(CONTRACT_TEMPLATE_FILE, "w") as f:
            f.write(DEFAULT_TEMPLATE)
        log.info(f"Created default {CONTRACT_TEMPLATE_FILE} — edit it to customise.")
    with open(CONTRACT_TEMPLATE_FILE, "r") as f:
        return f.read()


def build_extract_prompt(form_text):
    return f"""Extract new client onboarding details from this text.

Return ONLY valid JSON with these exact keys:
  ClientName          — full name of the new client contact
  CompanyName         — the client's company name
  ClientEmail         — their email address
  ServiceDescription  — a one-line description of the service requested
  Fee                 — the agreed fee if mentioned, else "To be confirmed"

Text:
---
{form_text[:2000]}
---
ONLY JSON. No markdown. Use "Not Found" for missing fields."""


def process_onboarding(gmail, cfg, message_id):
    headers, msg = core.gmail_get_message(gmail, message_id)
    sender       = headers.get("From", "Unknown")
    body_text    = core.gmail_get_body_text(msg)

    log.info(f"New onboarding request from {sender}")

    data = core.ask_deepseek(cfg["deepseek"]["api_key"], build_extract_prompt(body_text))
    if not data:
        log.error("AI extraction failed. Skipping.")
        core.gmail_mark_read(gmail, message_id)
        return False

    client_name = core.safe_text(data.get("ClientName"), "New Client")
    company     = core.safe_text(data.get("CompanyName"), "")
    client_mail = core.safe_text(data.get("ClientEmail"), sender)
    service     = core.safe_text(data.get("ServiceDescription"), "Services as discussed")
    fee         = core.safe_text(data.get("Fee"), "To be confirmed")

    # Fill the contract template — per-placeholder replace, so stray braces
    # in a user-edited template can never raise like str.format would.
    contract = (
        get_template()
        .replace("{Date}", core.timestamp())
        .replace("{CompanyName}", cfg["business"]["name"])
        .replace("{ClientName}", client_name)
        .replace("{ServiceDescription}", service)
        .replace("{Fee}", fee)
    )

    # Save a copy to the archive
    core.archive_file(cfg["settings"]["archive_folder"],
                      contract.encode("utf-8"),
                      f"Contract_{client_name.replace(' ', '_')}.txt")

    # Email the contract to the client
    core.gmail_send(
        gmail, client_mail, cfg["gmail"]["watch_inbox"],
        f"Your service agreement with {cfg['business']['name']}",
        f"Dear {client_name},\n\nThank you for choosing us. "
        f"Please find your service agreement below.\n\n"
        f"{'='*50}\n{contract}\n{'='*50}\n\n"
        f"Please reply to confirm and we'll get started.\n\n"
        f"Best regards,\n{cfg['business']['name']}"
    )
    log.info(f"Contract emailed to {client_mail}.")

    # Log to contracts sheet
    # Canonical Contract_Log columns: Date | Client | Email | Service | Fee | Status | Contract Sent
    core.sheets_append_row(
        cfg["google_sheets"]["sheet_id"],
        cfg["google_sheets"]["tabs"]["contracts"],
        [core.timestamp(), client_name, client_mail, service, fee, "Sent", core.timestamp()]
    )

    # Alert the owner
    core.gmail_send(
        gmail, cfg["gmail"]["alert_email"], cfg["gmail"]["watch_inbox"],
        f"GAOS: Contract sent to {client_name}",
        f"A contract has been generated and emailed.\n\n"
        f"Client:  {client_name}\nCompany: {company}\n"
        f"Service: {service}\nFee:     {fee}\n\nLogged: {core.timestamp()}"
    )

    core.gmail_mark_read(gmail, message_id)
    return True



CONTRACT_QUERY = 'is:unread (subject:"new client" OR subject:onboarding OR subject:"sign up")'

def scan(gmail, cfg):
    """Called by gaos_engine.py each poll cycle."""
    for e in core.gmail_search(gmail, CONTRACT_QUERY):
        try:
            process_onboarding(gmail, cfg, e["id"])
        except Exception as ex:
            log.error(f"Contract sender error: {ex}")


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    get_template()  # ensure template exists
    log.info("module_05_contract_sender: Watching for new client onboarding requests.")
    core.run_loop(lambda: scan(gmail, cfg),
                  cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
