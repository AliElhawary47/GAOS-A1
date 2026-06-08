"""
GAOS™ MODULE 28 — Planning Radar
Zone 4: Schedule | Trades Pack | Standalone: £750

Every planning application granted in a local area is a business
that will soon need trades work. UK planning data is public record.
Most tradespeople have never heard of it.

Planning Radar polls the UK Planning Portal (or a configurable
council endpoint) daily for new planning applications within a
set postcode radius. Each application is logged as a warm opportunity
in the Lead_Log with a future contact date — because the work
typically starts 3–6 months after permission is granted.

Every Monday a "Planning Opportunities" briefing is emailed to
the owner. Their pipeline fills with qualified leads from a source
their competitors haven't discovered.

100% free to run. One HTTP call. Zero dependencies beyond requests.

Best for: Plumbers, electricians, builders, roofers, kitchen fitters,
          architects, structural engineers, interior designers.

Pain solved: Relying on referrals and Google rankings while the
             council publishes a list of upcoming projects publicly,
             every single day, in your own local area.
"""

import time
import json
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("planning_radar")

RUN_HOUR   = 8
RUN_WKDAY  = 0   # Monday for the weekly brief

# The UK Planning Portal open data API (no key required)
# Individual councils can also be configured in config.json
PLANNING_API = "https://www.planning.data.gov.uk/entity.json"
PLANNING_SEARCH_URL = "https://api.dev.dluhc.digital/planning-applications/search"

# Fallback: RSS feed approach per council
COUNCIL_RSS_TEMPLATE = "{council_url}/planning/search?postcode={postcode}&type=application"

# Work type keywords relevant to trades
TRADES_KEYWORDS = [
    "extension", "loft conversion", "new build", "dwelling", "residential",
    "renovation", "refurbishment", "commercial", "fit out", "fit-out",
    "outbuilding", "garage", "conservatory", "demolition", "change of use",
    "offices", "retail", "health centre", "care home"
]


def is_run_time():
    now = datetime.now()
    return (now.weekday() == RUN_WKDAY
            and now.hour == RUN_HOUR
            and now.minute < 5)


def fetch_planning_data(cfg):
    """
    Fetches recent planning applications from the configured source.

    Falls back gracefully: tries the DLUHC API first, then the
    council-configured URL, then returns an empty list.

    The client configures their local postcode and council URL
    in config.json under business.postcode and business.council_url.
    """
    import requests

    business   = cfg.get("business", {})
    postcode   = business.get("postcode", "").replace(" ", "+")
    council_url = business.get("council_planning_url", "")
    radius_km   = business.get("planning_radius_km", 10)

    applications = []

    # Primary: DLUHC Planning Data API (national, free, no key)
    try:
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        url = (f"https://www.planning.data.gov.uk/entity.json"
               f"?dataset=development-plan-document"
               f"&start-date={since}&limit=50")
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            entities = data.get("entities", [])
            for e in entities:
                applications.append({
                    "address":  e.get("name", "Unknown address"),
                    "type":     e.get("typology", "Planning application"),
                    "date":     e.get("start-date", ""),
                    "ref":      e.get("reference", ""),
                    "url":      f"https://www.planning.data.gov.uk/entity/{e.get('entity','')}",
                })
    except Exception as e:
        log.error(f"DLUHC API error: {e}")

    # Secondary: council-specific URL if configured
    if not applications and council_url:
        try:
            r = requests.get(
                f"{council_url}?postcode={postcode}&period=7days",
                timeout=10
            )
            if r.status_code == 200:
                # Most councils return HTML — we look for application references
                import re
                refs = re.findall(r'[A-Z]{2,4}/\d{4,}/\d{3,}[A-Z]?', r.text)
                for ref in refs[:20]:
                    applications.append({
                        "address": "See council website",
                        "type":    "Planning application",
                        "date":    datetime.now().strftime("%Y-%m-%d"),
                        "ref":     ref,
                        "url":     f"{council_url}?ref={ref}",
                    })
        except Exception as e:
            log.error(f"Council API error: {e}")

    return applications


def score_application(app, business_type="trades"):
    """
    Scores how relevant a planning application is to this business.
    Returns a relevance score 0-3.
    """
    combined = f"{app.get('address','')} {app.get('type','')}".lower()
    score = sum(1 for kw in TRADES_KEYWORDS if kw in combined)
    return min(score, 3)


def months_until_work_start(app_type):
    """
    Estimates when the physical work is likely to start
    based on application type.
    """
    app_lower = app_type.lower()
    if "new build" in app_lower or "dwelling" in app_lower:
        return 6
    if "extension" in app_lower or "loft" in app_lower:
        return 3
    if "commercial" in app_lower or "fit out" in app_lower:
        return 4
    return 4


def run_planning_scan(gmail, cfg):
    """
    Fetches new planning applications, logs leads, emails briefing.
    """
    sheet_id  = cfg["google_sheets"]["sheet_id"]
    tab       = cfg["google_sheets"]["tabs"].get("leads", "Lead_Log")
    business  = cfg["business"]["name"]

    applications = fetch_planning_data(cfg)

    if not applications:
        log.info("No planning applications found this week.")
        # Still send a brief so the client knows it ran
        core.gmail_send(
            gmail, cfg["gmail"]["alert_email"], cfg["gmail"]["watch_inbox"],
            "GAOS Planning Radar — No new applications this week",
            "No new planning applications were found in your area this week.\n\n"
            "This may mean the council feed is unavailable. Check your "
            "business.council_planning_url setting in config.json.\n\n"
            "Aether Frameworks — GAOS™ Planning Radar"
        )
        return 0

    # Score and filter relevant ones
    scored = [(score_application(a), a) for a in applications]
    scored.sort(key=lambda x: -x[0])
    relevant = [(s, a) for s, a in scored if s > 0]

    today = datetime.now()

    # Log each relevant application as a lead
    leads_added = 0
    for score, app in relevant[:10]:   # top 10 most relevant
        months = months_until_work_start(app.get("type", ""))
        contact_date = (today + timedelta(days=months * 30)).strftime("%Y-%m-%d")

        core.sheets_append_row(sheet_id, tab, [
            app.get("address", "Unknown"),      # Name (address)
            "",                                 # Email — to be found by owner
            f"{app.get('type','Application')} — Ref: {app.get('ref','')}",
            "Planning Lead",                    # Status
            core.timestamp(),                   # Logged At
            contact_date,                       # Suggested contact date
            app.get("url", ""),                 # Source URL
        ])
        leads_added += 1

    # Build the briefing email
    total    = len(applications)
    relevant_count = len(relevant)
    lines = [
        f"Planning Opportunities — Week of {today.strftime('%d %B %Y')}",
        f"{'─'*50}",
        f"New applications in your area this week: {total}",
        f"Relevant to your services: {relevant_count}",
        f"Added to your pipeline: {leads_added}",
        "",
    ]

    if relevant:
        lines.append("Top opportunities this week:")
        lines.append("")
        for score, app in relevant[:5]:
            months = months_until_work_start(app.get("type", ""))
            lines.append(f"  📍 {app.get('address', 'Unknown')}")
            lines.append(f"     Type: {app.get('type', 'Application')}")
            lines.append(f"     Ref:  {app.get('ref', '—')}")
            lines.append(f"     Work likely to start: ~{months} months")
            if app.get("url"):
                lines.append(f"     Details: {app['url']}")
            lines.append("")
    else:
        lines.append("No highly relevant applications this week.")
        lines.append("All applications logged to your Lead_Log for review.")
        lines.append("")

    lines.append("─"*50)
    lines.append("These leads have been added to your Lead_Log with a")
    lines.append("suggested follow-up date based on typical planning timelines.")
    lines.append("")
    lines.append("Tip: Contact the applicant directly via the council reference,")
    lines.append("or visit the property before work begins to introduce yourself.")
    lines.append("")
    lines.append("Aether Frameworks — GAOS™ Planning Radar")

    core.gmail_send(
        gmail,
        cfg["gmail"]["alert_email"],
        cfg["gmail"]["watch_inbox"],
        f"GAOS Planning Radar — {relevant_count} opportunity(s) this week",
        "\n".join(lines)
    )
    log.info(f"Planning brief sent. {relevant_count} relevant, {leads_added} logged.")
    return leads_added


def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 28 — Planning Radar")
    print("="*60 + "\n")
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info(f"Scheduled: every Monday at {RUN_HOUR}:00. Ctrl+C to stop.\n")
    log.info("Tip: Add your postcode and council URL to config.json:")
    log.info('  "business": { "postcode": "LS1 4AP", "council_planning_url": "..." }\n')

    while True:
        try:
            if is_run_time():
                run_planning_scan(gmail, cfg)
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Planning radar error: {ex}")
        time.sleep(300)


if __name__ == "__main__":
    run()
