"""
GAOS™ MODULE 19 — Monthly Invoice Generator
Zone 4: Schedule | Standalone: £1,100 | In: GAOS™ Enterprise

On the 1st of every month, reads a Retainer_Clients sheet and
automatically generates and emails a plain-text invoice to each
active retainer client. Logs every invoice sent to the Invoice_Log.

Sheet tab required: Retainer_Clients
Columns: Client Name | Client Email | Service Description | Monthly Fee | Currency | Active | Last Invoiced

Target client: Consultants, accountants, agencies — anyone with monthly retainers.
Pain solved:   Manually creating and sending the same invoices every month.
"""

import time
from datetime import datetime
import gaos_core as core

log = core.get_logger("invoice_generator")

SEND_HOUR = 8
LAST_INVOICED_COL = 7


def is_invoice_day():
    now = datetime.now()
    return now.day == 1 and now.hour == SEND_HOUR and now.minute < 5


def generate_invoice_text(client_name, service, fee, currency, invoice_date, business_name):
    month_str = invoice_date.strftime("%B %Y")
    inv_num   = invoice_date.strftime("INV-%Y%m")
    return (
        f"INVOICE\n"
        f"{'─'*40}\n"
        f"Invoice Number: {inv_num}\n"
        f"Date:           {invoice_date.strftime('%d %B %Y')}\n\n"
        f"From: {business_name}\n"
        f"To:   {client_name}\n\n"
        f"{'─'*40}\n"
        f"Service:  {service} — {month_str}\n"
        f"Amount:   {currency}{fee}\n"
        f"{'─'*40}\n\n"
        f"Payment is due within 14 days of this invoice.\n\n"
        f"Thank you for your continued business.\n\n"
        f"{business_name}"
    )


def run_monthly_invoicing(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("retainer_clients", "Retainer_Clients")
    rows     = core.sheets_read_all(sheet_id, tab)
    today    = datetime.now()
    sent     = 0

    for i, row in enumerate(rows):
        active  = str(row.get("Active", "yes")).strip().lower()
        client  = str(row.get("Client Name",       "")).strip()
        email   = str(row.get("Client Email",      "")).strip()
        service = str(row.get("Service Description","Monthly services")).strip()
        fee     = str(row.get("Monthly Fee",        "0")).strip()
        currency= str(row.get("Currency",           "£")).strip()

        if active not in ("yes","true","1","y") or not email:
            continue

        invoice_text = generate_invoice_text(
            client, service, fee, currency, today, cfg["business"]["name"]
        )

        core.gmail_send(
            gmail, email, cfg["gmail"]["watch_inbox"],
            f"Invoice for {today.strftime('%B %Y')} — {cfg['business']['name']}",
            f"Dear {client},\n\nPlease find your invoice for "
            f"{today.strftime('%B %Y')} below.\n\n{invoice_text}"
        )
        log.info(f"Invoice sent to {client} ({email}) — {currency}{fee}")

        # Log to Invoice_Log
        core.sheets_append_row(
            sheet_id,
            cfg["google_sheets"]["tabs"].get("invoices", "Invoice_Log"),
            [client, today.strftime("%Y-%m-%d"), f"{currency}{fee}", "N/A",
             email, core.timestamp()]
        )

        # Update last invoiced date
        core.sheets_update_cell(sheet_id, tab, i + 2, LAST_INVOICED_COL,
                                today.strftime("%Y-%m-%d"))
        sent += 1

    return sent


def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 19 - Monthly Invoice Generator")
    print("="*60 + "\n")
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info(f"Scheduled: 1st of every month at {SEND_HOUR}:00am. Ctrl+C to stop.\n")

    while True:
        try:
            if is_invoice_day():
                n = run_monthly_invoicing(gmail, cfg)
                log.info(f"Sent {n} monthly invoice(s)." if n else "No active retainers found.")
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Error: {ex}")
        time.sleep(300)


if __name__ == "__main__":
    run()
