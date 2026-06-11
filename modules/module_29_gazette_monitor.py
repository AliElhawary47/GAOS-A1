"""
GAOS™ MODULE 29 — Gazette Monitor
Zone 0: Sense | Standalone: £900 | In: Enterprise

Reads the London Gazette — the UK's official public record — every morning
and cross-references its notices against your client and supplier lists.

Two types of notice monitored:

  1. CORPORATE INSOLVENCY — winding-up petitions and orders,
     liquidations, administrations. Cross-reference against
     Invoice_Log and Clients to catch bad debts before they
     become uncollectable. (Companies House strike-off notices
     are published as bulk Gazette supplements without structured
     data, so the winding-up petition — which precedes them — is
     the earliest structured warning available.)

  2. ESTATE NOTICES — probate creditor notices for recently deceased.
     For legal firms and estate professionals: these are warm leads
     arriving daily, publicly, for free.

The Gazette API is free, Crown Copyright, Open Government Licence.
No API key required. No rate limits documented.

API: https://www.thegazette.co.uk/all-notices/notice/data.json
     ?noticetypes=<code>&start-publish-date=YYYY-MM-DD
     Notices are returned under the "entry" key.

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

GAZETTE_API = "https://www.thegazette.co.uk/all-notices/notice/data.json"

# Notice type codes used by the Gazette data feed (verified live):
#   2450 — Corporate Insolvency (umbrella: winding-up petitions/orders,
#          liquidator appointments, administrations)
#   2903 — Deceased Estates (probate creditor notices)
NOTICE_TYPES = {
    "insolvency": "2450",
    "estate":     "2903",
}




def fetch_gazette_notices(notice_type_code, days_back=1):
    """
    Fetches recent notices from the London Gazette data feed.
    Returns a list of normalised notice dicts:
    {"name", "content", "url", "category"}.
    """
    import requests
    since = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    params = {
        "noticetypes": notice_type_code,
        "start-publish-date": since,
        "results-page-size": 50,
    }
    try:
        r = requests.get(GAZETTE_API, params=params, timeout=20)
        if r.status_code != 200:
            log.error(f"Gazette API returned {r.status_code}")
            return []
        entries = r.json().get("entry", [])
        notices = []
        for e in entries:
            category = e.get("category", "")
            if isinstance(category, dict):
                category = category.get("@term", "")
            notices.append({
                # title holds the company / deceased person's name
                "name":     str(e.get("title", "")).replace("/n", "").strip(),
                "content":  str(e.get("content", "")),
                # "id" is already a full URI like
                # https://www.thegazette.co.uk/id/notice/5151815
                "url":      str(e.get("id", "")),
                "category": str(category),
            })
        return notices
    except Exception as e:
        log.error(f"Gazette fetch error: {e}")
        return []


def extract_company_names(notices):
    """Extracts company names from normalised Gazette notice records."""
    names = set()
    for n in notices:
        if n.get("name"):
            names.add(n["name"].strip())
        body = n.get("content", "")
        if body:
            # Company names in Gazette notice bodies are ALL CAPS followed
            # by a legal suffix. Case-sensitive on purpose — IGNORECASE
            # over-captures surrounding lowercase prose.
            found = re.findall(
                r'[A-Z][A-Z &\'\-]{2,}\s+(?:LIMITED|LTD|PLC|LLP)',
                str(body)
            )
            names.update(f.strip() for f in found)
    return {n for n in names if len(n) >= 4}


def fuzzy_match(gazette_name, client_name):
    """
    Simple fuzzy match — checks if a Gazette name meaningfully overlaps
    with a known client or supplier name.
    Returns True if likely the same entity.
    """
    gn = re.sub(r'\b(LIMITED|LTD|PLC|LLP)\b', '', gazette_name.upper()).strip()
    cn = re.sub(r'\b(LIMITED|LTD|PLC|LLP)\b', '', client_name.upper()).strip()
    # Empty strings must never match anything
    if len(gn) < 4 or len(cn) < 4:
        return False
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
        known = {str(r.get("Client", "")).strip() for r in invoices
                 if r.get("Client")}
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
                "message": (f"'{m['known_as']}' appears in today's corporate insolvency "
                            f"notices (winding-up petition/order, liquidation or "
                            f"administration). Check for outstanding invoices and "
                            f"consider chasing immediately. Insolvency administrators "
                            f"typically accept creditor claims for 14–28 days after notice."),
            })
        log.warning(f"Insolvency match(es) found: {len(insolvency_matches)}")
    else:
        log.info(f"  {len(insolvency_names)} insolvency notices — no matches with your contacts.")

    # --- Estate/probate scan (log as leads rather than risk alerts) ---
    log.info("Scanning Gazette: estate notices...")
    estate_notices = fetch_gazette_notices(NOTICE_TYPES["estate"])
    log.info(f"  {len(estate_notices)} estate notices found — logged to leads.")

    if estate_notices:
        _log_estate_leads(cfg, estate_notices)

    # --- Send alert if any risk matches found ---
    if alerts:
        _log_gazette_hits(cfg, alerts)
        _send_risk_alert(gmail, cfg, alerts, today)
    else:
        log.info("Gazette scan complete. No risk matches found today.")

    return len(alerts)


def _log_gazette_hits(cfg, alerts):
    """Logs each risk match to the Gazette_Hits tab.
    Canonical columns: Date | Company | Notice Type | Details | Actioned"""
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("gazette_hits", "Gazette_Hits")
    for a in alerts:
        try:
            core.sheets_append_row(sheet_id, tab, [
                core.timestamp(), a["gazette"], a["type"],
                f"Matches your contact: {a['known']}", ""
            ])
        except Exception:
            pass


def _log_estate_leads(cfg, notices):
    """Logs estate notices as leads for legal/probate professionals.
    Canonical Lead_Log order:
    [Date, From, Email, Subject, Summary, Status, Chase Sent, Source]"""
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("leads", "Lead_Log")
    for n in notices[:10]:   # cap at 10
        name = n.get("name") or "Estate notice"
        # strip HTML tags from the notice body for the summary
        summary = re.sub(r"<[^>]+>", " ", n.get("content", ""))
        summary = re.sub(r"\s+", " ", summary).strip()[:150]
        try:
            core.sheets_append_row(sheet_id, tab, [
                core.timestamp(), name, "", "Gazette estate notice",
                summary, "Gazette Estate Lead", "",
                n.get("url", ""),   # already a full URI from the feed
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
    core.run_loop(lambda: _tick(gmail, cfg),
                  cfg.get("settings", {}).get("check_every_seconds", 300))


if __name__ == "__main__":
    run()
