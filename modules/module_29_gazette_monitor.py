"""
GAOS™ MODULE 29 — Gazette Monitor
Zone 0: Sense | Standalone: £900 | In: Enterprise

Reads the London Gazette — the UK's official public record — every morning
and cross-references its notices against your client and supplier lists.

Three types of notice monitored:

  1. INSOLVENCY — liquidations, administrations, bankruptcies.
     Cross-reference against Invoice_Log to catch bad debts before
     they become uncollectable.

  2. STRIKE-OFF WARNINGS — companies failing to file accounts, 2 months
     from dissolution. Cross-reference against supplier list for
     continuity risk.

  3. ESTATE NOTICES — probate creditor notices for recently deceased.
     For legal firms and estate professionals: these are warm leads
     arriving daily, publicly, for free.

The Gazette API is free, Crown Copyright, Open Government Licence.
No API key required. No rate limits documented.

API: https://www.thegazette.co.uk/notice/search?notice-type=...
     Returns JSON. Completely free.

Target: Any business that invoices other businesses (insolvency/strike-off),
        solicitors and estate professionals (probate pipeline).
Pain:   The client who owed you £8,000 filed for administration this morning.
        You didn't know. You won't chase. The window closes in 14 days.
"""

import re
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("gazette_monitor")

RUN_HOUR = 7   # Before Daily Digest so digest can include any alerts

GAZETTE_API = "https://www.thegazette.co.uk/notice/search"

# Notice type codes used by the Gazette API
NOTICE_TYPES = {
    "insolvency":    "2700",   # Insolvency: liquidation, administration, bankruptcy
    "strike_off":    "2750",   # Companies about to be struck off
    "estate":        "2600",   # Wills, probate, estate notices
}




def fetch_gazette_notices(notice_type_code, days_back=1):
    """
    Fetches recent notices from the London Gazette API.
    Returns a list of notice dicts.
    """
    import requests
    since = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    params = {
        "notice-type": notice_type_code,
        "start-publish-date": since,
        "results-page-size": 50,
        "format": "application/json",
    }
    try:
        r = requests.get(GAZETTE_API, params=params, timeout=15,
                         headers={"Accept": "application/json"})
        if r.status_code != 200:
            log.error(f"Gazette API returned {r.status_code}")
            return []
        data = r.json()
        # Gazette returns notices under 'results' or '_embedded'
        results = (data.get("results") or
                   data.get("_embedded", {}).get("notices", []) or
                   data.get("notices", []))
        return results if isinstance(results, list) else []
    except Exception as e:
        log.error(f"Gazette fetch error: {e}")
        return []


def extract_company_names(notices):
    """Extracts company names from Gazette notice records."""
    names = set()
    for n in notices:
        # Try multiple possible fields
        for field in ("companyName", "company_name", "name", "title", "subject"):
            val = n.get(field, "")
            if val and isinstance(val, str):
                names.add(val.strip())
                break
        # Also try to extract from body text if present
        body = n.get("body", n.get("content", n.get("noticeText", "")))
        if body:
            # Company names in Gazette are typically ALL CAPS or Title Case followed by Ltd/PLC
            found = re.findall(
                r'[A-Z][A-Z &\'\-]{2,}\s+(?:LIMITED|LTD|PLC|LLP|PARTNERSHIP)',
                str(body), re.IGNORECASE
            )
            names.update(f.strip() for f in found)
    return names


def fuzzy_match(gazette_name, client_name):
    """
    Simple fuzzy match — checks if a Gazette name meaningfully overlaps
    with a known client or supplier name.
    Returns True if likely the same entity.
    """
    gn = re.sub(r'\b(LIMITED|LTD|PLC|LLP)\b', '', gazette_name.upper()).strip()
    cn = re.sub(r'\b(LIMITED|LTD|PLC|LLP)\b', '', client_name.upper()).strip()
    # Match if one contains the other (handles abbrev/short names)
    return gn in cn or cn in gn or (len(gn) > 6 and gn[:6] == cn[:6])


def cross_reference(gazette_names, cfg):
    """
    Looks for matches between Gazette company names and the client's
    known contacts (from Invoice_Log and Clients sheet).
    Returns list of match dicts.
    """
    sheet_id = cfg["google_sheets"]["sheet_id"]
    matches  = []

    # Read known vendors from Invoice_Log
    try:
        invoices = core.sheets_read_all(
            sheet_id, cfg["google_sheets"]["tabs"].get("invoices", "Invoice_Log")
        )
        known = {str(r.get("Vendor", "")).strip() for r in invoices
                 if r.get("Vendor")}
    except Exception:
        known = set()

    # Read known clients from Clients sheet
    try:
        clients = core.sheets_read_all(
            sheet_id, cfg["google_sheets"]["tabs"].get("clients", "Clients")
        )
        known.update(str(r.get("Name", "")).strip() for r in clients if r.get("Name"))
    except Exception:
        pass

    # Match
    for gname in gazette_names:
        for kname in known:
            if kname and fuzzy_match(gname, kname):
                matches.append({"gazette": gname, "known_as": kname})
                break

    return matches


def run_gazette_scan(gmail, cfg):
    """Runs the daily Gazette scan and emails any alerts."""
    business = cfg["business"]["name"]
    today    = datetime.now().strftime("%A %d %B %Y")
    alerts   = []

    # --- Insolvency scan ---
    log.info("Scanning Gazette: insolvency notices...")
    insolvency_notices = fetch_gazette_notices(NOTICE_TYPES["insolvency"])
    insolvency_names   = extract_company_names(insolvency_notices)
    insolvency_matches = cross_reference(insolvency_names, cfg)

    if insolvency_matches:
        for m in insolvency_matches:
            alerts.append({
                "type":    "INSOLVENCY",
                "gazette": m["gazette"],
                "known":   m["known_as"],
                "message": (f"'{m['known_as']}' appears in today's insolvency notices. "
                            f"Check for outstanding invoices and consider chasing immediately. "
                            f"Insolvency administrators typically accept creditor claims "
                            f"for 14–28 days after notice."),
            })
        log.warning(f"Insolvency match(es) found: {len(insolvency_matches)}")
    else:
        log.info(f"  {len(insolvency_names)} insolvency notices — no matches with your contacts.")

    # --- Strike-off scan ---
    log.info("Scanning Gazette: strike-off warnings...")
    strikeoff_notices = fetch_gazette_notices(NOTICE_TYPES["strike_off"])
    strikeoff_names   = extract_company_names(strikeoff_notices)
    strikeoff_matches = cross_reference(strikeoff_names, cfg)

    if strikeoff_matches:
        for m in strikeoff_matches:
            alerts.append({
                "type":    "STRIKE-OFF WARNING",
                "gazette": m["gazette"],
                "known":   m["known_as"],
                "message": (f"'{m['known_as']}' has received a compulsory strike-off warning "
                            f"from Companies House (published in today's Gazette). "
                            f"They have approximately 2 months before dissolution. "
                            f"If they are a supplier, consider finding alternatives. "
                            f"If they owe you money, chase this debt now."),
            })
        log.warning(f"Strike-off match(es) found: {len(strikeoff_matches)}")
    else:
        log.info(f"  {len(strikeoff_names)} strike-off notices — no matches.")

    # --- Estate/probate scan (log as leads rather than risk alerts) ---
    log.info("Scanning Gazette: estate notices...")
    estate_notices = fetch_gazette_notices(NOTICE_TYPES["estate"])
    log.info(f"  {len(estate_notices)} estate notices found — logged to leads.")

    if estate_notices:
        _log_estate_leads(cfg, estate_notices)

    # --- Send alert if any risk matches found ---
    if alerts:
        _send_risk_alert(gmail, cfg, alerts, today)
    else:
        log.info("Gazette scan complete. No risk matches found today.")

    return len(alerts)


def _log_estate_leads(cfg, notices):
    """Logs estate notices as leads for legal/probate professionals."""
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("leads", "Lead_Log")
    for n in notices[:10]:   # cap at 10
        name    = n.get("companyName", n.get("title", "Estate notice"))
        ref     = n.get("id", n.get("noticeCode", ""))
        summary = str(n.get("body", n.get("content", "")))[:120]
        try:
            core.sheets_append_row(sheet_id, tab, [
                name, "", summary,
                "Gazette Estate Lead", core.timestamp(),
                f"https://www.thegazette.co.uk/notice/{ref}"
            ])
        except Exception:
            pass


def _send_risk_alert(gmail, cfg, alerts, today):
    """Sends an immediate risk alert email for insolvency/strike-off matches."""
    lines = [
        "GAOS GAZETTE ALERT",
        f"Date: {today}",
        f"Business: {cfg['business']['name']}",
        f"{'─'*50}",
        f"",
        f"{len(alerts)} risk notice(s) matched your known contacts:",
        "",
    ]
    for a in alerts:
        lines.append(f"[{a['type']}]")
        lines.append(f"In Gazette as: {a['gazette']}")
        lines.append(f"Matches your contact: {a['known']}")
        lines.append(f"")
        lines.append(f"{a['message']}")
        lines.append(f"")
        lines.append(f"{'─'*50}")
        lines.append("")

    lines.append("View full Gazette notices at:")
    lines.append("https://www.thegazette.co.uk/insolvency")
    lines.append("")
    lines.append("Aether Frameworks — GAOS™ Gazette Monitor")

    core.gmail_send(
        gmail,
        cfg["gmail"]["alert_email"],
        cfg["gmail"]["watch_inbox"],
        f"⚠ GAOS Gazette Alert — {len(alerts)} risk notice(s) require attention",
        "\n".join(lines)
    )
    log.info(f"Risk alert sent: {len(alerts)} notice(s)")


def _tick(gmail, cfg):
    if core.should_run_at(RUN_HOUR):
        run_gazette_scan(gmail, cfg)


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info(f"Scheduled: daily at {RUN_HOUR}:00. Ctrl+C to stop.")
    core.run_loop(lambda: _tick(gmail, cfg), cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
