"""
╔══════════════════════════════════════════════════════════════╗
║   GAOS™ MODULE 04 — Google Review Auto-Booster              ║
║   Standalone: £600  |  In: GAOS™ Core, Pro, Enterprise      ║
╠══════════════════════════════════════════════════════════════╣
║   The owner marks a job "Completed" in a Google Sheet.      ║
║   GAOS™ waits a set delay, then texts the customer a        ║
║   friendly request for a Google review with a direct link.  ║
║                                                             ║
║   Target client:  Gyms, salons, mechanics, local trades     ║
║   Pain solved:    Forgetting to ask happy customers for     ║
║                   reviews — the #1 driver of local ranking  ║
╚══════════════════════════════════════════════════════════════╝

How it works:
  The client keeps a sheet (tab: Completed_Jobs) with columns:
    Date | Client | Email | Phone | Service | Status | Review Sent
  When Status = "Completed" and Review Sent is blank,
  GAOS sends the review request and marks "Review Sent" as "Sent".
"""

import gaos_core as core

log = core.get_logger("review_requester")


def build_message(customer_name, business_name, review_link):
    """A warm, non-pushy review request."""
    return (
        f"Hi {customer_name}, thank you for choosing {business_name}! "
        f"If you were happy with our work, would you mind leaving us a quick "
        f"review? It really helps us: {review_link}"
    )


def check_completed_jobs(cfg, gmail=None):
    """Reads the jobs sheet and sends review requests for new completions."""
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"]["reviews"]

    rows = core.sheets_read_all(sheet_id, tab)
    if not rows:
        log.info("No jobs found in sheet.")
        return 0

    tw           = cfg["twilio"]
    business     = cfg["business"]["name"]
    review_link  = cfg["business"]["google_review_link"]
    sent_count   = 0

    # Row 1 is headers, so sheet row = index + 2
    for i, row in enumerate(rows):
        status      = str(row.get("Status", "")).strip().lower()
        already     = str(row.get("Review Sent", "")).strip().lower()
        customer    = str(row.get("Client", "")).strip()
        mobile      = str(row.get("Phone", "")).strip()
        email       = str(row.get("Email", "")).strip()

        if status != "completed" or already == "sent":
            continue

        message = build_message(customer or "there", business, review_link)
        ok = False

        if mobile:
            if "YOUR_" in tw["account_sid"]:
                # Don't mark the row — the customer still gets their request
                # once Twilio is configured.
                log.warning(f"Twilio not configured — would text {customer}: {message}")
                continue
            ok = core.send_sms(tw["account_sid"], tw["auth_token"],
                               tw["from_number"], mobile, message)
            if ok:
                log.info(f"Review request sent to {customer} ({mobile}).")
            else:
                log.error(f"Failed to text {customer}.")
        elif email:
            if gmail is None:
                gmail = core.connect_gmail()
            if gmail is None:
                log.error(f"No phone for {customer} and Gmail unavailable — skipping.")
                continue
            ok = core.gmail_send(gmail, email, cfg["gmail"]["watch_inbox"],
                                 f"How did we do, {customer or 'there'}?", message)
            if ok:
                log.info(f"Review request emailed to {customer} ({email}).")
            else:
                log.error(f"Failed to email {customer}.")
        else:
            continue

        if ok:
            # Mark "Review Sent" (by header name) only after a confirmed send
            core.sheets_update_cell(sheet_id, tab, i + 2, "Review Sent", "Sent")
            sent_count += 1

    return sent_count


def run():
    cfg = core.load_config()
    gmail = core.connect_gmail()
    log.info("module_04_review_requester: Watching for completed jobs.")
    core.run_loop(lambda: check_completed_jobs(cfg, gmail),
                  cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
