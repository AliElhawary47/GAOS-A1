"""
GAOS™ MODULE 11 — Document Chaser
Zone 2: Chase | Standalone: £800 | In: GAOS™ Pro, Enterprise

Monitors a sheet of outstanding document requests — ID, proof of address,
signed forms, compliance docs — and sends polite automated chase emails
to clients who haven't responded within a set number of days.

Sheet tab required: Pending_Documents
Columns: Client Name | Client Email | Document Required | Requested Date | Received | Chased | Notes

Target client: Accountants, solicitors, recruiters, mortgage brokers.
Pain solved:   Hours spent manually chasing compliance and onboarding documents.
"""

import time
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("document_chaser")

CHASE_AFTER_DAYS = 3
CHASE_COL        = 6   # "Chased" column (1-based)


def build_chase(client, doc_required, business_name):
    return (
        f"Dear {client},\n\n"
        f"I hope you are well. I am writing to follow up on the "
        f"outstanding document request: {doc_required}.\n\n"
        f"We need this document to proceed with your case. "
        f"Could you please send it over at your earliest convenience?\n\n"
        f"If you have already sent it, please disregard this message "
        f"and accept our apologies for the inconvenience.\n\n"
        f"Thank you for your cooperation.\n\nBest regards,\n{business_name}"
    )


def check_pending_documents(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("pending_documents", "Pending_Documents")
    rows     = core.sheets_read_all(sheet_id, tab)
    chased   = 0

    for i, row in enumerate(rows):
        received  = str(row.get("Received",         "")).strip().lower()
        chased_v  = str(row.get("Chased",            "")).strip().lower()
        client    = str(row.get("Client Name",       "")).strip()
        email     = str(row.get("Client Email",      "")).strip()
        doc       = str(row.get("Document Required", "documents")).strip()
        req_date  = str(row.get("Requested Date",    "")).strip()

        if received in ("yes","received","✓") or chased_v == "sent" or not email:
            continue

        try:
            req_dt = datetime.strptime(req_date[:10], "%Y-%m-%d")
        except ValueError:
            continue

        if datetime.now() - req_dt < timedelta(days=CHASE_AFTER_DAYS):
            continue

        log.info(f"Chasing {doc} from {client} ({email})")
        body = build_chase(client or "there", doc, cfg["business"]["name"])
        core.gmail_send(gmail, email, cfg["gmail"]["watch_inbox"],
                        f"Outstanding document request: {doc}", body)
        core.sheets_update_cell(sheet_id, tab, i + 2, CHASE_COL, "Sent")
        chased += 1

    return chased


def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 11 - Document Chaser")
    print("="*60 + "\n")
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Watching for outstanding document requests. Ctrl+C to stop.\n")

    while True:
        try:
            n = check_pending_documents(gmail, cfg)
            log.info(f"Chased {n} document request(s)." if n else "No outstanding documents.")
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Loop error: {ex}")
        time.sleep(cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
