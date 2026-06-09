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

from datetime import datetime
import gaos_core as core

log = core.get_logger("invoice_generator")

SEND_HOUR = 8
LAST_INVOICED_COL = 7


def generate_invoice_text(client_name, service, fee, currency, invoice_date, business_name, seq=1):
    month_str = invoice_date.strftime("%B %Y")
    inv_num   = f"INV-{invoice_date.strftime('%Y%m')}-{seq:03d}"
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
    sheet_id  = cfg["google_sheets"]["sheet_id"]
    tab       = cfg["google_sheets"]["tabs"].get("retainer_clients", "Retainer_Clients")
    inv_tab   = cfg["google_sheets"]["tabs"].get("invoices", "Invoice_Log")
    rows      = core.sheets_read_all(sheet_id, tab)
    today     = datetime.now()
    sent      = 0

    # Base the sequence on invoices already in the log for this month
    month_pfx = today.strftime("%Y-%m")
    try:
        inv_rows = core.sheets_read_all(sheet_id, inv_tab)
        seq = sum(1 for r in inv_rows if str(r.get("InvoiceDate","")).startswith(month_pfx))
    except Exception:
        seq = 0

    for i, row in enumerate(rows):
        active  = str(row.get("Active", "yes")).strip().lower()
        client  = str(row.get("Client Name",       "")).strip()
        email   = str(row.get("Client Email",      "")).strip()
        service = str(row.get("Service Description","Monthly services")).strip()
        fee     = str(row.get("Monthly Fee",        "0")).strip()
        currency= str(row.get("Currency",           "£")).strip()

        if active not in ("yes","true","1","y") or not email:
            continue

        seq += 1
        invoice_text = generate_invoice_text(
            client, service, fee, currency, today, cfg["business"]["name"], seq
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


def _tick(gmail, cfg):
    if core.should_run_at(SEND_HOUR, day_of_month=1):
        n = run_monthly_invoicing(gmail, cfg)
        log.info(f"Sent {n} monthly invoice(s)." if n else "No active retainers found.")


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info(f"Scheduled: 1st of every month at {SEND_HOUR}:00. Ctrl+C to stop.")
    core.run_loop(lambda: _tick(gmail, cfg), cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
