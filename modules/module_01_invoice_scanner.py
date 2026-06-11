"""
╔══════════════════════════════════════════════════════════════╗
║   GAOS™ MODULE 01 — Smart Invoice & Receipt Tracker         ║
║   Standalone: £1,200  |  In: GAOS™ Pro, Enterprise          ║
╠══════════════════════════════════════════════════════════════╣
║   Watches inbox for PDF invoices → AI extracts the data →   ║
║   logs to Google Sheets → archives PDF → alerts the owner.  ║
║                                                             ║
║   Target client:  Accountants, lawyers, consultants         ║
║   Pain solved:    Manual bookkeeping data entry             ║
╚══════════════════════════════════════════════════════════════╝
"""

import re
import gaos_core as core
from modules import module_25_gaos_learn as learn

log = core.get_logger("invoice_scanner")


def build_prompt(pdf_text):
    """The exact instruction sent to DeepSeek to read an invoice."""
    return f"""You are a professional accountant AI.
Extract the key fields from this invoice text.

Return ONLY valid JSON with these exact keys:
  VendorName    — supplier/company that issued the invoice
  InvoiceDate   — date in YYYY-MM-DD format if possible
  InvoiceNumber — invoice/reference number, or "Not Found"
  TotalAmount   — total payable, include currency symbol
  TaxAmount     — VAT/tax amount, or "N/A" if not present

Rules: ONLY JSON. No markdown. No backticks. Use "Not Found" if a field is missing.

Invoice text:
---
{pdf_text[:4000]}
---"""


def _is_duplicate(cfg, vendor: str, invoice_date: str, invoice_number: str) -> bool:
    """Returns True if this vendor+date or invoice number already exists in the log."""
    try:
        rows = core.sheets_read_all(
            cfg["google_sheets"]["sheet_id"],
            cfg["google_sheets"]["tabs"]["invoices"]
        )
        vendor_l  = vendor.lower()
        inv_num_l = invoice_number.lower()
        for row in rows:
            row_vendor = str(row.get("Client","")).strip().lower()
            row_date   = str(row.get("Invoice Date","")).strip()
            row_num    = str(row.get("Invoice ID","")).strip().lower()
            if row_vendor == vendor_l and row_date == invoice_date:
                return True
            if inv_num_l not in ("", "not found") and row_num == inv_num_l:
                return True
    except Exception:
        pass
    return False


def _anomaly_note(cfg, amount_str: str) -> str:
    """Returns a warning string if the amount is unusually high vs the learned average."""
    try:
        context   = learn.get_context(cfg)
        avg_match = re.search(r"Average invoice value is [£$€]([\d,]+)", context)
        if not avg_match:
            return ""
        avg_val = float(avg_match.group(1).replace(",", ""))
        amt_num = float(re.sub(r"[^\d.]", "", amount_str) or 0)
        if amt_num > 0 and avg_val > 0 and amt_num > avg_val * 2.5:
            return f"⚠ Unusual amount (avg is £{avg_val:.0f})"
    except Exception:
        pass
    return ""


def process_invoice(gmail, cfg, message_id):
    """Full pipeline for one invoice email."""
    headers, _ = core.gmail_get_message(gmail, message_id)
    sender     = headers.get("From", "Unknown")

    pdf_bytes, filename = core.gmail_download_pdf(gmail, message_id)
    if not pdf_bytes:
        log.warning("No PDF attachment found. Skipping.")
        core.gmail_mark_read(gmail, message_id)
        return False

    log.info(f"Processing '{filename}' from {sender}")

    text = core.extract_pdf_text(pdf_bytes)
    if not text:
        log.warning("PDF has no readable text (scanned image?). Skipping.")
        core.gmail_mark_read(gmail, message_id)
        return False

    # AI extraction
    data = core.ask_deepseek(cfg["deepseek"]["api_key"], build_prompt(text))
    if not data:
        data = {"VendorName": "Extraction Failed", "InvoiceDate": "N/A",
                "InvoiceNumber": "N/A", "TotalAmount": "N/A", "TaxAmount": "N/A"}

    vendor        = core.safe_text(data.get("VendorName"), "Unknown")
    invoice_date  = core.safe_text(data.get("InvoiceDate"))
    invoice_num   = core.safe_text(data.get("InvoiceNumber"))
    total_amount  = core.safe_text(data.get("TotalAmount"))

    # Duplicate guard: skip if same vendor+date or invoice number already logged
    if _is_duplicate(cfg, vendor, invoice_date, invoice_num):
        log.warning(f"Duplicate invoice skipped: {vendor} {invoice_date} ({invoice_num})")
        core.gmail_mark_read(gmail, message_id)
        return False

    # Anomaly check: flag if amount is unusually high vs learned average
    notes = _anomaly_note(cfg, total_amount)
    if notes:
        log.warning(f"Invoice anomaly: {vendor} {total_amount} — {notes}")

    # Log to Sheets — canonical Invoice_Log columns:
    # Invoice ID | Client | Client Email | Amount | Invoice Date | Status | Chase Sent | Notes
    # Status "Received" = supplier invoice WE received; module 08 must never chase these.
    email_match  = re.search(r"[\w.+-]+@[\w.-]+", sender)
    sender_email = email_match.group(0) if email_match else sender
    invoice_id   = "" if invoice_num.lower() in ("", "not found", "n/a") else invoice_num
    core.sheets_append_row(
        cfg["google_sheets"]["sheet_id"],
        cfg["google_sheets"]["tabs"]["invoices"],
        [
            invoice_id,
            vendor,
            sender_email,
            total_amount,
            invoice_date,
            "Received",
            "",
            notes,
        ]
    )

    # Archive PDF
    core.archive_file(cfg["settings"]["archive_folder"], pdf_bytes, f"{vendor}_{filename}")

    # Alert owner
    anomaly_line = f"\n{notes}\n" if notes else ""
    body = (
        f"GAOS Invoice Processed\n{'-'*40}\n\n"
        f"Vendor:    {vendor}\n"
        f"Date:      {invoice_date}\n"
        f"Ref:       {invoice_num}\n"
        f"Amount:    {total_amount}\n"
        f"Tax:       {core.safe_text(data.get('TaxAmount'))}\n"
        f"{anomaly_line}"
        f"\nFrom:      {sender}\nLogged:    {core.timestamp()}\n\n"
        f"Aether Frameworks - GAOS Module 01"
    )
    core.gmail_send(gmail, cfg["gmail"]["alert_email"], cfg["gmail"]["watch_inbox"],
                    f"GAOS Invoice: {vendor}", body)

    core.gmail_mark_read(gmail, message_id)
    return True



def scan(gmail, cfg):
    """Called by gaos_engine.py each poll cycle — no loop, no sleep."""
    emails = core.gmail_search(gmail, "is:unread has:attachment filename:pdf")
    for e in emails:
        try:
            process_invoice(gmail, cfg, e["id"])
        except Exception as ex:
            log.error(f"Invoice scan error: {ex}")


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("module_01_invoice_scanner: Gmail connected. Watching for invoices.")
    core.run_loop(lambda: scan(gmail, cfg),
                  cfg.get("settings", {}).get("check_every_seconds", 300))


if __name__ == "__main__":
    run()
