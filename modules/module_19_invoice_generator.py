"""
GAOS™ MODULE 19 — Monthly Invoice Generator
Zone 4: Schedule | Standalone: £1,100 | In: GAOS™ Enterprise

On the 1st of every month, reads a Retainer_Clients sheet and
automatically generates and emails a plain-text invoice to each
active retainer client. Logs every invoice sent to the Invoice_Log.

Sheet tab required: Retainer_Clients
Columns: Name | Email | Amount | Billing Day | Status | Last Invoice

Target client: Consultants, accountants, agencies — anyone with monthly retainers.
Pain solved:   Manually creating and sending the same invoices every month.
"""

import re
from datetime import datetime
import gaos_core as core

log = core.get_logger("invoice_generator")

SEND_HOUR = 8


def generate_invoice_text(client_name, service, fee, currency, invoice_date, business_name, inv_num):
    month_str = invoice_date.strftime("%B %Y")
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

    # Base the sequence on invoice IDs already in the log for this month
    month_pfx = today.strftime("%Y%m")
    this_month = today.strftime("%Y-%m")
    id_pattern = re.compile(rf"INV-{month_pfx}-(\d+)$")
    seq = 0
    try:
        inv_rows = core.sheets_read_all(sheet_id, inv_tab)
        for r in inv_rows:
            match = id_pattern.match(str(r.get("Invoice ID", "")).strip())
            if match:
                seq = max(seq, int(match.group(1)))
    except Exception:
        seq = 0

    for i, row in enumerate(rows):
        status   = str(row.get("Status", "")).strip().lower()
        client   = str(row.get("Name",   "")).strip()
        email    = str(row.get("Email",  "")).strip()
        fee      = str(row.get("Amount", "0")).strip()
        last_inv = str(row.get("Last Invoice", "")).strip()
        currency = "£"

        if status not in ("", "active", "yes", "true", "1", "y") or not email:
            continue

        # DOUBLE-BILL GUARD: skip anyone already invoiced this month
        if last_inv.startswith(this_month):
            continue

        seq += 1
        invoice_id   = f"INV-{month_pfx}-{seq:03d}"
        invoice_text = generate_invoice_text(
            client, "Monthly retainer", fee, currency, today,
            cfg["business"]["name"], invoice_id
        )

        ok = core.gmail_send(
            gmail, email, cfg["gmail"]["watch_inbox"],
            f"Invoice for {today.strftime('%B %Y')} — {cfg['business']['name']}",
            f"Dear {client},\n\nPlease find your invoice for "
            f"{today.strftime('%B %Y')} below.\n\n{invoice_text}"
        )
        if not ok:
            log.error(f"Invoice email to {client} ({email}) failed — not logged, will retry")
            seq -= 1   # number was never sent, reuse it
            continue

        log.info(f"Invoice sent to {client} ({email}) — {currency}{fee}")

        # Log to Invoice_Log (canonical column order) — Status "Unpaid" so
        # module 08's chaser picks it up
        core.sheets_append_row(
            sheet_id, inv_tab,
            [invoice_id, client, email, fee, today.strftime("%Y-%m-%d"),
             "Unpaid", "", "Monthly retainer invoice"]
        )

        # Update last invoiced date — this is the double-bill guard marker
        core.sheets_update_cell(sheet_id, tab, i + 2, "Last Invoice",
                                core.timestamp())
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
    core.run_loop(lambda: _tick(gmail, cfg),
                  cfg.get("settings", {}).get("check_every_seconds", 300))


if __name__ == "__main__":
    run()
