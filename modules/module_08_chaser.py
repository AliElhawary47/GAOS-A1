"""
GAOS™ MODULE 08 — Unified Item Chaser
Zone 2: Chase | In: Virtual Admin + Virtual Finance + Virtual Sales
Standalone: £850

Consolidates three previously separate chase modules:
  • Payment Chaser   — overdue invoices (14-day threshold)
  • Proposal Chaser  — unanswered proposals (5-day threshold)
  • Document Chaser  — outstanding compliance docs (3-day threshold)

Each chaser is defined as a ChaseConfig entry in CHASERS. The same
generic engine processes all of them in one poll cycle, so a single
module handles all three follow-up loops with zero repeated code.

Sheets required:
  Invoice_Log       — Vendor | Invoice Date | Amount | ... | Status | Chase Sent
  Proposals         — Client Name | Client Email | Proposal Date | Value | Status | Chase Sent
  Pending_Documents — Client Name | Client Email | Document Required | Requested Date | Received | Chased
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Tuple

import gaos_core as core

log = core.get_logger("item_chaser")


# ── EMAIL BUILDERS ────────────────────────────────────────────────

def build_payment_email(row: dict, cfg: dict) -> Tuple[str, str]:
    vendor  = core.safe_text(row.get("Vendor"), "there")
    amount  = core.safe_text(row.get("Amount"), "the outstanding amount")
    date    = core.safe_text(row.get("Invoice Date"), "recently")
    biz     = cfg["business"]["name"]
    subject = f"Payment reminder — {amount}"
    body = (
        f"Dear {vendor},\n\n"
        f"I hope you are well. I wanted to follow up regarding the invoice "
        f"dated {date} for {amount}.\n\n"
        f"According to our records this invoice is still outstanding. "
        f"If you have already arranged payment, please disregard this message.\n\n"
        f"If you have any questions or need a copy of the invoice, "
        f"please do not hesitate to get in touch.\n\n"
        f"Many thanks,\n{biz}"
    )
    return subject, body


def build_proposal_email(row: dict, cfg: dict) -> Tuple[str, str]:
    client = core.safe_text(row.get("Client Name"), "there")
    value  = core.safe_text(row.get("Value"), "")
    biz    = cfg["business"]["name"]
    subject = "Following up on your proposal"
    body = (
        f"Hi {client},\n\n"
        f"I wanted to check in on the proposal I sent over recently"
        f"{f' (valued at {value})' if value else ''}.\n\n"
        f"Have you had a chance to review it? I am happy to answer any "
        f"questions or jump on a quick call to talk through the details.\n\n"
        f"Looking forward to hearing from you.\n\nBest regards,\n{biz}"
    )
    return subject, body


def build_document_email(row: dict, cfg: dict) -> Tuple[str, str]:
    client = core.safe_text(row.get("Client Name"), "there")
    doc    = core.safe_text(row.get("Document Required"), "outstanding document")
    biz    = cfg["business"]["name"]
    subject = f"Outstanding document request: {doc}"
    body = (
        f"Dear {client},\n\n"
        f"I hope you are well. I am writing to follow up on the "
        f"outstanding document request: {doc}.\n\n"
        f"We need this document to proceed with your case. "
        f"Could you please send it over at your earliest convenience?\n\n"
        f"If you have already sent it, please disregard this message "
        f"and accept our apologies for the inconvenience.\n\n"
        f"Thank you for your cooperation.\n\nBest regards,\n{biz}"
    )
    return subject, body


# ── CHASE CONFIG ──────────────────────────────────────────────────

@dataclass
class ChaseConfig:
    name:         str
    tab_key:      str
    date_col:     str
    status_col:   str
    done_values:  tuple
    chase_col:    str
    email_col:    str
    name_col:     str
    days:         int
    build_email:  Callable


CHASERS = [
    ChaseConfig(
        name        = "Payment Chaser",
        tab_key     = "invoices",
        date_col    = "Invoice Date",
        status_col  = "Status",
        done_values = ("paid", "cancelled", "void"),
        chase_col   = "Chase Sent",
        email_col   = "Source Email",
        name_col    = "Vendor",
        days        = 14,
        build_email = build_payment_email,
    ),
    ChaseConfig(
        name        = "Proposal Chaser",
        tab_key     = "proposals",
        date_col    = "Proposal Date",
        status_col  = "Status",
        done_values = ("accepted", "declined", "cancelled"),
        chase_col   = "Chase Sent",
        email_col   = "Client Email",
        name_col    = "Client Name",
        days        = 5,
        build_email = build_proposal_email,
    ),
    ChaseConfig(
        name        = "Document Chaser",
        tab_key     = "pending_documents",
        date_col    = "Requested Date",
        status_col  = "Received",
        done_values = ("yes", "received", "✓"),
        chase_col   = "Chased",
        email_col   = "Client Email",
        name_col    = "Client Name",
        days        = 3,
        build_email = build_document_email,
    ),
]


# ── GENERIC CHASE ENGINE ──────────────────────────────────────────

def check_and_chase(gmail, cfg, chaser: ChaseConfig) -> int:
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get(chaser.tab_key, chaser.tab_key)
    rows     = core.sheets_read_all(sheet_id, tab)
    sent     = 0

    for i, row in enumerate(rows):
        status    = str(row.get(chaser.status_col, "")).strip().lower()
        chased    = str(row.get(chaser.chase_col,  "")).strip().lower()
        email     = str(row.get(chaser.email_col,  "")).strip()
        name      = str(row.get(chaser.name_col,   "there")).strip()
        date_str  = str(row.get(chaser.date_col,   "")).strip()

        if status in chaser.done_values or chased == "sent" or not email:
            continue

        try:
            item_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
        except ValueError:
            continue

        if datetime.now() - item_date < timedelta(days=chaser.days):
            continue

        log.info(f"[{chaser.name}] chasing {name} ({email})")
        subject, body = chaser.build_email(row, cfg)
        core.gmail_send(gmail, email, cfg["gmail"]["watch_inbox"], subject, body)
        core.sheets_update_cell(sheet_id, tab, i + 2, chaser.chase_col, "Sent")
        sent += 1

    return sent


def run_all_chasers(gmail, cfg):
    total = 0
    for chaser in CHASERS:
        try:
            n = check_and_chase(gmail, cfg, chaser)
            if n:
                log.info(f"[{chaser.name}] sent {n} chase(s).")
            total += n
        except Exception as exc:
            log.error(f"[{chaser.name}] error: {exc}")
    if not total:
        log.info("No items to chase across all queues.")


# ── ENTRY POINT ───────────────────────────────────────────────────

def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Unified Item Chaser active — payments, proposals, documents.")
    core.run_loop(
        lambda: run_all_chasers(gmail, cfg),
        cfg["settings"]["check_every_seconds"]
    )


if __name__ == "__main__":
    run()
