"""
GAOS™ MODULE 08 — Unified Item Chaser
Zone 2: Chase | In: Virtual Admin + Virtual Finance + Virtual Sales
Standalone: £850

Consolidates three previously separate chase modules:
  • Payment Chaser   — overdue invoices (14/21/30-day escalating tiers)
  • Proposal Chaser  — unanswered proposals (5-day threshold)
  • Document Chaser  — outstanding compliance docs (3-day threshold)

Payment chaser escalates tone automatically:
  Tier 1 (14 days) — polite reminder
  Tier 2 (21 days) — firm follow-up
  Tier 3 (30 days) — final notice

A duplicate-send guard searches Gmail sent folder before every chase
to prevent accidental double-chasing if the owner already emailed manually.

Sheets required:
  Invoice_Log       — Invoice ID | Client | Client Email | Amount | Invoice Date | Status | Chase Sent | Notes
  Proposals         — Proposal Date | Client Name | Client Email | Value | Status | Chase Sent
  Pending_Documents — Requested Date | Client Name | Email | Document | Received | Chased

Only invoices the business ISSUED are chased — rows with Status
"Received" are supplier invoices logged by module 01 and are skipped.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, List, Tuple

import gaos_core as core


def _get_late_payers(cfg) -> List[str]:
    """Returns a lowercase list of vendor names learned as habitual late payers."""
    try:
        from modules import module_25_gaos_learn as learn
        context = learn.get_context(cfg)
        m = re.search(r"Suppliers with previous late payment chases: ([^\n.]+)", context)
        if m:
            return [n.strip().lower() for n in m.group(1).split(",") if n.strip()]
    except Exception:
        pass
    return []

log = core.get_logger("item_chaser")


# ── EMAIL BUILDERS ────────────────────────────────────────────────

def build_payment_email(row: dict, cfg: dict, level: int = 1) -> Tuple[str, str]:
    vendor  = core.safe_text(row.get("Client"), "there")
    amount  = core.safe_text(row.get("Amount"), "the outstanding amount")
    date    = core.safe_text(row.get("Invoice Date"), "recently")
    biz     = cfg["business"]["name"]

    if level == 1:
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
    elif level == 2:
        subject = f"Second payment reminder — {amount} now overdue"
        body = (
            f"Dear {vendor},\n\n"
            f"I am following up again on the invoice dated {date} for {amount}, "
            f"which remains unpaid.\n\n"
            f"We have not received any response to our previous reminder. "
            f"Please arrange payment at your earliest convenience or contact us "
            f"to discuss if there is an issue.\n\n"
            f"If payment has already been sent, please let us know the date and "
            f"payment method so we can confirm receipt.\n\n"
            f"Kind regards,\n{biz}"
        )
    else:
        subject = f"FINAL NOTICE — {amount} overdue"
        body = (
            f"Dear {vendor},\n\n"
            f"This is a final notice regarding the outstanding invoice dated "
            f"{date} for {amount}.\n\n"
            f"Despite two previous reminders, this invoice remains unpaid. "
            f"Please arrange immediate payment or contact us urgently to avoid "
            f"further action.\n\n"
            f"If you believe you have received this notice in error, please "
            f"contact us immediately with proof of payment.\n\n"
            f"Regards,\n{biz}"
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
    doc    = core.safe_text(row.get("Document"), "outstanding document")
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
    escalate:     bool = False
    # escalation_days[i] = minimum days overdue to trigger tier i+1
    escalation_days: List[int] = field(default_factory=lambda: [14, 21, 30])


CHASERS = [
    ChaseConfig(
        name            = "Payment Chaser",
        tab_key         = "invoices",
        date_col        = "Invoice Date",
        status_col      = "Status",
        # "received" = supplier invoice logged by module 01 — never chase those
        done_values     = ("paid", "cancelled", "void", "received"),
        chase_col       = "Chase Sent",
        email_col       = "Client Email",
        name_col        = "Client",
        days            = 14,
        build_email     = build_payment_email,
        escalate        = True,
        escalation_days = [14, 21, 30],
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
        email_col   = "Email",
        name_col    = "Client Name",
        days        = 3,
        build_email = build_document_email,
    ),
]


# ── GENERIC CHASE ENGINE ──────────────────────────────────────────

def _recently_emailed(gmail, email: str) -> bool:
    """Returns True if an email was sent to this address in the last 48 hours."""
    try:
        results = core.gmail_search(gmail, f"to:{email} in:sent newer_than:2d", max_results=1)
        return len(results) > 0
    except Exception:
        return False


def _current_chase_level(chased: str) -> int:
    """Maps Chase Sent cell value to the last completed tier (0 = none sent)."""
    chased = chased.lower().strip()
    if chased in ("", "no"):
        return 0
    if chased == "sent-2":
        return 2
    if chased == "sent-3":
        return 3
    # "sent", "sent-1", or any legacy value treated as tier 1
    return 1


def check_and_chase(gmail, cfg, chaser: ChaseConfig, late_payers: List[str] = None) -> int:
    sheet_id  = cfg["google_sheets"]["sheet_id"]
    tab       = cfg["google_sheets"]["tabs"].get(chaser.tab_key, chaser.tab_key)
    rows      = core.sheets_read_all(sheet_id, tab)
    sent      = 0
    days_now  = datetime.now()

    for i, row in enumerate(rows):
        status   = str(row.get(chaser.status_col, "")).strip().lower()
        chased   = str(row.get(chaser.chase_col,  "")).strip()
        email    = str(row.get(chaser.email_col,  "")).strip()
        name     = str(row.get(chaser.name_col,   "there")).strip()
        date_str = str(row.get(chaser.date_col,   "")).strip()

        if status in chaser.done_values or not email:
            continue

        item_date = core.parse_date(date_str)
        if not item_date:
            continue

        days_elapsed = (days_now - item_date).days

        if chaser.escalate:
            level = _current_chase_level(chased)
            # Already at max tier — nothing left to send
            if level >= len(chaser.escalation_days):
                continue
            # Known late payers: trigger first chase at 7 days instead of default threshold
            threshold = chaser.escalation_days[level]
            if level == 0 and late_payers and any(lp in name.lower() for lp in late_payers):
                threshold = min(threshold, 7)
                log.info(f"[{chaser.name}] Known late payer: {name} — using {threshold}-day threshold")
            if days_elapsed < threshold:
                continue
            next_level = level + 1
        else:
            # Single-chase behaviour (proposals, documents)
            if chased.lower() == "sent" or days_elapsed < chaser.days:
                continue
            next_level = None

        # Duplicate-send guard: skip if already manually emailed recently
        if _recently_emailed(gmail, email):
            log.info(f"[{chaser.name}] skipping {name} — sent mail in last 48h")
            continue

        log.info(f"[{chaser.name}] chasing {name} ({email})"
                 + (f" tier {next_level}" if next_level else ""))

        if chaser.escalate:
            subject, body = chaser.build_email(row, cfg, level=next_level)
            mark = f"Sent-{next_level}"
        else:
            subject, body = chaser.build_email(row, cfg)
            mark = "Sent"

        if core.gmail_send(gmail, email, cfg["gmail"]["watch_inbox"], subject, body):
            core.sheets_update_cell(sheet_id, tab, i + 2, chaser.chase_col, mark)
            sent += 1
        else:
            log.warning(f"[{chaser.name}] send to {email} failed — will retry next poll")

    return sent


def run_all_chasers(gmail, cfg):
    late_payers = _get_late_payers(cfg)
    total = 0
    for chaser in CHASERS:
        try:
            n = check_and_chase(gmail, cfg, chaser, late_payers)
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
        cfg.get("settings", {}).get("check_every_seconds", 300)
    )


if __name__ == "__main__":
    run()
