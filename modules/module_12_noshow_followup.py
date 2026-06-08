"""
GAOS™ MODULE 12 — No-Show Follow-Up
Zone 2: Chase | Standalone: £600 | In: GAOS™ Core, Pro, Enterprise

When an appointment is marked as "No-Show" in the Appointments sheet,
GAOS automatically sends a warm, non-confrontational rebooking message
to the client and logs the follow-up.

Sheet tab required: Appointments
Columns: Client Name | Mobile | Email | Date | Time | Status | 24h Sent | 2h Sent | Followup Sent

Target client: Clinics, salons, personal trainers, consultants.
Pain solved:   Revenue lost from missed appointments that are never rebooked.
"""

import gaos_core as core

log = core.get_logger("noshow_followup")

FOLLOWUP_COL = 9   # "Followup Sent" column (1-based)


def build_followup(client, business_name, booking_link=""):
    link_text = f"\n\nBook your next slot here: {booking_link}" if booking_link else ""
    return (
        f"Hi {client},\n\n"
        f"We noticed you were unable to make your recent appointment with us "
        f"at {business_name}. We hope everything is okay!\n\n"
        f"We would love to get you rebooked at a time that suits you better."
        f"{link_text}\n\n"
        f"Just reply to this email or give us a call and we will get you sorted.\n\n"
        f"Best regards,\n{business_name}"
    )


def check_noshows(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("appointments", "Appointments")
    rows     = core.sheets_read_all(sheet_id, tab)
    sent     = 0

    booking_link = cfg["business"].get("booking_link", "")

    for i, row in enumerate(rows):
        status    = str(row.get("Status",         "")).strip().lower()
        followup  = str(row.get("Followup Sent",  "")).strip().lower()
        client    = str(row.get("Client Name",    "")).strip()
        mobile    = str(row.get("Mobile",         "")).strip()
        email     = str(row.get("Email",          "")).strip()

        if status != "no-show" or followup == "sent" or (not mobile and not email):
            continue

        log.info(f"Sending rebooking message to no-show: {client}")
        body = build_followup(client or "there", cfg["business"]["name"], booking_link)

        # SMS
        tw = cfg["twilio"]
        if mobile and "YOUR_" not in tw["account_sid"]:
            sms_body = (f"Hi {client}, we missed you today at {cfg['business']['name']}! "
                        f"We'd love to rebook you. Reply here or call us.")
            core.send_sms(tw["account_sid"], tw["auth_token"],
                          tw["from_number"], mobile, sms_body)

        # Email
        if email:
            core.gmail_send(gmail, email, cfg["gmail"]["watch_inbox"],
                            f"We missed you — {cfg['business']['name']}", body)

        core.sheets_update_cell(sheet_id, tab, i + 2, FOLLOWUP_COL, "Sent")
        sent += 1

    return sent


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("module_12_noshow_followup: Watching for no-shows.")
    core.run_loop(lambda: check_noshows(gmail, cfg),
                  cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
