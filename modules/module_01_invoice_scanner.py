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

import time
import gaos_core as core

log = core.get_logger("invoice_scanner")


def build_prompt(pdf_text):
    """The exact instruction sent to DeepSeek to read an invoice."""
    return f"""You are a professional accountant AI.
Extract the key fields from this invoice text.

Return ONLY valid JSON with these exact keys:
  VendorName   — supplier/company that issued the invoice
  InvoiceDate  — date in YYYY-MM-DD format if possible
  TotalAmount  — total payable, include currency symbol
  TaxAmount    — VAT/tax amount, or "N/A" if not present

Rules: ONLY JSON. No markdown. No backticks. Use "Not Found" if a field is missing.

Invoice text:
---
{pdf_text[:4000]}
---"""


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
                "TotalAmount": "N/A", "TaxAmount": "N/A"}

    # Log to Sheets
    core.sheets_append_row(
        cfg["google_sheets"]["sheet_id"],
        cfg["google_sheets"]["tabs"]["invoices"],
        [
            core.safe_text(data.get("VendorName")),
            core.safe_text(data.get("InvoiceDate")),
            core.safe_text(data.get("TotalAmount")),
            core.safe_text(data.get("TaxAmount")),
            sender,
            core.timestamp(),
        ]
    )

    # Archive PDF
    vendor = core.safe_text(data.get("VendorName"), "Unknown")
    core.archive_file(cfg["settings"]["archive_folder"], pdf_bytes, f"{vendor}_{filename}")

    # Alert owner
    body = (
        f"GAOS Invoice Processed\n{'-'*40}\n\n"
        f"Vendor:    {core.safe_text(data.get('VendorName'))}\n"
        f"Date:      {core.safe_text(data.get('InvoiceDate'))}\n"
        f"Amount:    {core.safe_text(data.get('TotalAmount'))}\n"
        f"Tax:       {core.safe_text(data.get('TaxAmount'))}\n\n"
        f"From:      {sender}\nLogged:    {core.timestamp()}\n\n"
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
    print("\n" + "="*60)
    print("  GAOS MODULE 01 - Smart Invoice & Receipt Tracker")
    print("="*60 + "\n")

    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Gmail connected. Watching for invoices. Ctrl+C to stop.\n")

    count = 0
    while True:
        try:
            emails = core.gmail_search(gmail, "is:unread has:attachment filename:pdf")
            for e in emails:
                if process_invoice(gmail, cfg, e["id"]):
                    count += 1
                    log.info(f"Invoice #{count} complete.\n")
            if not emails:
                log.info(f"No new invoices. Next check in {cfg['settings']['check_every_seconds']//60} min.")
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Loop error: {ex}")
        time.sleep(cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
