"""
GAOS™ MODULE 09 — Proposal Chaser
Zone 2: Chase | Standalone: £750 | In: GAOS™ Pro, Enterprise

Watches a Proposals sheet for quotes or proposals that have been sent
but not responded to. After a configurable number of days, sends a
warm follow-up email and marks it as chased.

Sheet tab required: Proposals
Columns: Client Name | Client Email | Proposal Date | Value | Status | Chase Sent | Logged At

Target client: Consultants, estate agents, agencies, builders.
Pain solved:   Forgetting to follow up on sent proposals — silent revenue loss.
"""

import time
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("proposal_chaser")

CHASE_AFTER_DAYS = 5
CHASE_COL        = 6    # "Chase Sent" column (1-based)


def build_followup(client_name, value, business_name):
    return (
        f"Hi {client_name},\n\n"
        f"I wanted to check in on the proposal I sent over recently"
        f"{f' (valued at {value})' if value and value != 'Not Found' else ''}.\n\n"
        f"Have you had a chance to review it? I am happy to answer any "
        f"questions or jump on a quick call to talk through the details.\n\n"
        f"Looking forward to hearing from you.\n\nBest regards,\n{business_name}"
    )


def check_proposals(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("proposals", "Proposals")
    rows     = core.sheets_read_all(sheet_id, tab)
    chased   = 0

    for i, row in enumerate(rows):
        status     = str(row.get("Status",      "sent")).strip().lower()
        chase_sent = str(row.get("Chase Sent",  "")).strip().lower()
        client     = str(row.get("Client Name", "there")).strip()
        email      = str(row.get("Client Email","")).strip()
        value      = str(row.get("Value",       "")).strip()
        sent_date  = str(row.get("Proposal Date","")).strip()

        if status in ("accepted","declined","cancelled") or chase_sent == "sent" or not email:
            continue

        try:
            proposal_dt = datetime.strptime(sent_date[:10], "%Y-%m-%d")
        except ValueError:
            continue

        if datetime.now() - proposal_dt < timedelta(days=CHASE_AFTER_DAYS):
            continue

        log.info(f"Chasing proposal for {client} ({email})")
        body = build_followup(client, value, cfg["business"]["name"])
        core.gmail_send(gmail, email, cfg["gmail"]["watch_inbox"],
                        f"Following up on your proposal", body)

        core.sheets_update_cell(sheet_id, tab, i + 2, CHASE_COL, "Sent")
        chased += 1

    return chased


def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 09 - Proposal Chaser")
    print("="*60 + "\n")
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Watching for unresponded proposals. Ctrl+C to stop.\n")

    while True:
        try:
            n = check_proposals(gmail, cfg)
            log.info(f"Chased {n} proposal(s)." if n else "No proposals to chase.")
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Loop error: {ex}")
        time.sleep(cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
