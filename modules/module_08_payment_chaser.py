"""
GAOS™ MODULE 08 — Payment Chaser
Zone 2: Chase | Standalone: £850 | In: GAOS™ Pro, Enterprise

Watches the Invoice_Log sheet for unpaid invoices that are overdue.
When an invoice has been sent but not paid after a set number of days,
GAOS automatically sends a polite, professional payment reminder email
and marks the invoice as chased so it is never double-sent.

Sheet tab required: Invoice_Log
Required columns: Vendor | Date | Amount | Tax | Source Email | Logged At | Status | Chase Sent

Target client: Any business that invoices clients — accountants, agencies, trades.
Pain solved:   Awkward manual chasing of late payments.
"""

import time
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("payment_chaser")

CHASE_AFTER_DAYS = 14   # send reminder if unpaid after this many days
CHASE_COL        = 8    # column index of "Chase Sent" in the sheet (1-based)
STATUS_COL       = 7    # column index of "Status"


def build_chase_email(vendor, amount, invoice_date, business_name):
    return (
        f"Dear {vendor},\n\n"
        f"I hope you are well. I wanted to follow up regarding invoice "
        f"dated {invoice_date} for {amount}.\n\n"
        f"According to our records this invoice is still outstanding. "
        f"If you have already arranged payment, please disregard this message.\n\n"
        f"If you have any questions or need a copy of the invoice, "
        f"please do not hesitate to get in touch.\n\n"
        f"Many thanks,\n{business_name}"
    )


def check_overdue_invoices(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"]["invoices"]
    rows     = core.sheets_read_all(sheet_id, tab)
    chased   = 0

    for i, row in enumerate(rows):
        status     = str(row.get("Status",     "")).strip().lower()
        chase_sent = str(row.get("Chase Sent", "")).strip().lower()
        vendor     = str(row.get("Vendor",     "")).strip()
        amount     = str(row.get("Amount",     "")).strip()
        source     = str(row.get("Source Email","")).strip()
        logged_at  = str(row.get("Logged At",  "")).strip()

        # Skip if already paid, already chased, or no contact email
        if status in ("paid", "cancelled") or chase_sent == "sent" or not source:
            continue

        # Parse the logged date and check if overdue
        try:
            invoice_date = datetime.strptime(logged_at[:10], "%Y-%m-%d")
        except ValueError:
            continue

        if datetime.now() - invoice_date < timedelta(days=CHASE_AFTER_DAYS):
            continue

        log.info(f"Overdue invoice: {vendor} ({amount}) — sending chase to {source}")

        body = build_chase_email(
            vendor, amount, invoice_date.strftime("%d %B %Y"),
            cfg["business"]["name"]
        )
        core.gmail_send(gmail, source, cfg["gmail"]["watch_inbox"],
                        f"Payment reminder — {amount}", body)

        # Mark as chased — row index is i+2 (1 header row + 0-indexed)
        core.sheets_update_cell(sheet_id, tab, i + 2, CHASE_COL, "Sent")
        chased += 1

    return chased


def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 08 - Payment Chaser")
    print("="*60 + "\n")

    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Watching for overdue invoices. Ctrl+C to stop.\n")

    while True:
        try:
            n = check_overdue_invoices(gmail, cfg)
            msg = f"Sent {n} payment reminder(s)." if n else "No overdue invoices found."
            log.info(msg)
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Loop error: {ex}")
        time.sleep(cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
