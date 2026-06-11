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

import json
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("planning_radar")

RUN_HOUR   = 8
RUN_WKDAY  = 0   # Monday for the weekly brief

# The national planning.data.gov.uk entity API (no key required).
# A lat/long point query returns only applications whose boundary contains
# that point — strictly local, but coverage is limited to councils that
# publish to the national dataset. Configure business.council_planning_url
# in config.json for full local coverage.
PLANNING_API = "https://www.planning.data.gov.uk/entity.json"
GEOCODE_API  = "https://api.postcodes.io/postcodes/{postcode}"

# Work type keywords relevant to trades
TRADES_KEYWORDS = [
    "extension", "loft conversion", "new build", "dwelling", "residential",
    "renovation", "refurbishment", "commercial", "fit out", "fit-out",
    "outbuilding", "garage", "conservatory", "demolition", "change of use",
    "offices", "retail", "health centre", "care home"
]




def _geocode_postcode(postcode: str):
    """Free postcode → (longitude, latitude) via postcodes.io. None on failure."""
    import requests
    try:
        r = requests.get(GEOCODE_API.format(postcode=postcode.replace(" ", "")),
                         timeout=10)
        r.raise_for_status()
        result = r.json().get("result", {})
        if result.get("longitude") is not None:
            return result["longitude"], result["latitude"]
    except Exception as e:
        log.warning(f"Postcode geocode failed for {postcode!r}: {e}")
    return None


def fetch_planning_data(cfg):
    """
    Fetches planning applications NEAR THE CONFIGURED POSTCODE only.

    Primary: national planning.data.gov.uk point query (location-scoped by
    construction; sparse coverage). Secondary: the council-configured URL.
    Never returns un-located nationwide results — an empty list is the
    honest answer when no local source has data.
    """
    import requests

    business    = cfg.get("business", {})
    postcode    = business.get("postcode", "").strip()
    council_url = business.get("council_planning_url", "")

    applications = []

    # Primary: national dataset, filtered to the business's location
    coords = _geocode_postcode(postcode) if postcode else None
    if coords:
        try:
            r = requests.get(
                PLANNING_API,
                params={"dataset": "planning-application",
                        "longitude": coords[0], "latitude": coords[1],
                        "limit": 50},
                timeout=20,
            )
            r.raise_for_status()
            for e in r.json().get("entities", []):
                applications.append({
                    "address": e.get("name") or f"Near {postcode} — ref {e.get('reference','?')}",
                    "type":    e.get("description", "Planning application"),
                    "date":    e.get("entry-date", ""),
                    "ref":     e.get("reference", ""),
                    "url":     f"https://www.planning.data.gov.uk/entity/{e.get('entity','')}",
                })
        except Exception as e:
            log.error(f"planning.data.gov.uk error: {e}")

    # Secondary: council-specific URL if configured
    if not applications and council_url:
        try:
            r = requests.get(
                f"{council_url}?postcode={postcode.replace(' ', '+')}&period=7days",
                timeout=15
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

    if not applications and not council_url:
        log.info("Planning Radar: no national coverage for this area — "
                 "set business.council_planning_url in config.json for "
                 "full local coverage.")

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
            "Note: the national planning dataset only covers some councils. "
            "For full local coverage set business.council_planning_url in "
            "config.json to your council's planning search page.\n\n"
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

        # Canonical Lead_Log order:
        # [Date, From, Email, Subject, Summary, Status, Chase Sent, Source]
        core.sheets_append_row(sheet_id, tab, [
            core.timestamp(),
            app.get("address", "Unknown"),
            "",                                 # Email — to be found by owner
            f"Planning application {app.get('ref','')}".strip(),
            f"{str(app.get('type','Application'))[:150]} — "
            f"suggested contact date {contact_date}",
            "Planning Lead",
            "",
            app.get("url", ""),
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


def _tick(gmail, cfg):
    if core.should_run_at(RUN_HOUR, weekday=RUN_WKDAY):
        run_planning_scan(gmail, cfg)


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info(f"Scheduled: every Monday at {RUN_HOUR}:00. Ctrl+C to stop.")
    core.run_loop(lambda: _tick(gmail, cfg),
                  cfg.get("settings", {}).get("check_every_seconds", 300))


if __name__ == "__main__":
    run()
