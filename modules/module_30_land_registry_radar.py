"""
GAOS™ MODULE 30 — Land Registry Radar
Zone 0: Sense | Standalone: £800 | Trades Pack | In: Enterprise

Downloads the Land Registry Price Paid Data — every property sold
in England and Wales, updated monthly, completely free — filters it
by the client's postcode area, scores each sale by renovation potential,
and surfaces the most relevant ones as warm leads in the Lead_Log.

A sold house is a future renovation project. Almost always.
This module makes that fact actionable, every month, for free.

The data includes: full address, price paid, date of transfer,
property type (detached, semi, terraced, flat), new build flag, tenure.

Free download: https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads
Format: CSV, updated 20th working day of each month.
No API key. No cost. Open Government Licence.

Target: Builders, plumbers, electricians, decorators, kitchen fitters,
        extension specialists, architects, interior designers.
Pain:   Relying on referrals while a monthly list of your most likely
        future clients is published for free by the government.
"""

import io
import csv
import re
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("land_registry_radar")

RUN_WEEKDAY = 0   # Monday
RUN_HOUR    = 9   # After gazette scan and digest

# Land Registry Price Paid Data — monthly CSV endpoint (verified live).
# The 'monthly update' file always contains the last month's transactions.
LR_RECENT_URL = "https://price-paid-data.publicdata.landregistry.gov.uk/pp-monthly-update-new-version.csv"

# Property type scoring for renovation potential
PROPERTY_SCORES = {
    "D": 4,   # Detached — highest renovation potential
    "S": 3,   # Semi-detached
    "T": 3,   # Terraced
    "F": 1,   # Flat/maisonette — lowest (usually no structural work)
    "O": 2,   # Other
}

# Price bracket scoring (higher price = more likely to invest in renovation)
def price_score(price):
    if price >= 600000: return 4
    if price >= 350000: return 3
    if price >= 200000: return 2
    if price >= 100000: return 1
    return 0




def get_postcode_prefix(postcode):
    """Returns the OUTWARD code (e.g. 'LS1' from 'LS1 4AP') for exact
    area matching. Stripping the space and regex-matching greedily would
    swallow the inward code ('LS1 4AP' → 'LS14A'), matching nothing."""
    parts = postcode.upper().strip().split()
    if parts:
        return parts[0]
    return postcode.upper().strip()


def _postcode_outward(csv_postcode):
    """Outward code of a CSV postcode cell ('LS1 4AP' → 'LS1')."""
    parts = str(csv_postcode).upper().strip().split()
    return parts[0] if parts else ""


def download_price_paid_data():
    """Downloads the monthly Land Registry Price Paid update CSV."""
    import requests
    log.info("Downloading Land Registry Price Paid data...")
    try:
        r = requests.get(LR_RECENT_URL, timeout=60)
        if r.status_code == 200:
            log.info(f"  Downloaded {len(r.content):,} bytes")
            return r.text
        log.error(f"Land Registry returned {r.status_code}")
        return None
    except Exception as e:
        log.error(f"Download error: {e}")
        return None


def parse_price_paid_csv(csv_text, postcode_prefix, days_back=35):
    """
    Parses the Land Registry CSV and returns relevant sales.
    Columns (LR format, no headers):
      0: Transaction ID
      1: Price
      2: Date of transfer
      3: Postcode
      4: Property type (D/S/T/F/O)
      5: New build (Y/N)
      6: Duration (F/L)
      7: PAON (primary addressable object name)
      8: SAON (secondary)
      9: Street
      10: Locality
      11: Town/City
      12: District
      13: County
      14: PPD category
      15: Record status
    """
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    results = []

    reader = csv.reader(io.StringIO(csv_text))
    for row in reader:
        try:
            if len(row) < 14:
                continue
            txid         = row[0].strip('"')
            price_str    = row[1].strip('"')
            date_str     = row[2].strip('"')[:10]
            postcode     = row[3].strip('"')
            prop_type    = row[4].strip('"').upper()
            new_build    = row[5].strip('"').upper() == "Y"
            paon         = row[7].strip('"')
            street       = row[9].strip('"')
            town         = row[11].strip('"')

            # Date filter
            if date_str < cutoff:
                continue

            # Postcode filter — exact outward-code match ('LS1' must not
            # also match LS10–LS19, so plain startswith is wrong)
            if _postcode_outward(postcode) != postcode_prefix.upper():
                continue

            price = int(price_str) if price_str.isdigit() else 0

            # Build address
            address_parts = [p for p in [paon, street, town, postcode] if p]
            address = ", ".join(address_parts)

            results.append({
                "id":        txid,
                "address":   address,
                "postcode":  postcode,
                "price":     price,
                "date":      date_str,
                "type":      prop_type,
                "new_build": new_build,
                "town":      town,
                "score":     PROPERTY_SCORES.get(prop_type, 1) + price_score(price),
            })
        except Exception:
            continue

    return results


def format_price(price):
    return f"£{price:,.0f}"


def contact_date_from_sale(sale_date_str):
    """Returns suggested first-contact date: 6 weeks after sale."""
    try:
        sale_dt = datetime.strptime(sale_date_str, "%Y-%m-%d")
        return (sale_dt + timedelta(weeks=6)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def run_radar(gmail, cfg):
    """Downloads Land Registry data and surfaces leads."""
    business = cfg["business"]["name"]
    postcode = cfg["business"].get("postcode", "")
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("leads", "Lead_Log")

    if not postcode:
        log.warning("No postcode configured. Add 'postcode' to business section in config.json")
        return 0

    prefix = get_postcode_prefix(postcode)
    log.info(f"Scanning Land Registry for postcode area: {prefix}...")

    csv_text = download_price_paid_data()
    if not csv_text:
        return 0

    sales = parse_price_paid_csv(csv_text, prefix)
    if not sales:
        log.info(f"No recent sales found in {prefix} area.")
        return 0

    # Sort by renovation score, highest first
    sales.sort(key=lambda x: -x["score"])

    # Filter: exclude flats for trades (configurable), exclude new builds
    # (new builds don't need renovation work immediately)
    prefer_type = cfg["business"].get("property_type_filter", "")
    if prefer_type:
        sales = [s for s in sales if s["type"] == prefer_type.upper()]
    else:
        sales = [s for s in sales if not s["new_build"]]

    # Dedupe: the monthly file overlaps weekly runs by design, so skip
    # transactions already logged (transaction ID lives in the
    # Land_Registry_Leads "Notes" column).
    lr_tab = cfg["google_sheets"]["tabs"].get("land_leads", "Land_Registry_Leads")
    try:
        existing_ids = {str(r.get("Notes", "")).strip()
                        for r in core.sheets_read_all(sheet_id, lr_tab)}
    except Exception:
        existing_ids = set()
    sales = [s for s in sales if s["id"] not in existing_ids]

    if not sales:
        log.info("All recent sales already logged — nothing new this week.")
        return 0

    # Log top 15 to Land_Registry_Leads + Lead_Log
    logged = 0
    for sale in sales[:15]:
        contact_date = contact_date_from_sale(sale["date"])
        note = (f"Land Registry: {sale['type']} sold {sale['date']} — "
                f"{format_price(sale['price'])}. "
                f"Renovation potential score: {sale['score']}/7. "
                f"Suggested first contact: {contact_date}")
        try:
            # Canonical Land_Registry_Leads:
            # [Date, Address, Price, Buyer, Seller, Status, Notes]
            core.sheets_append_row(sheet_id, lr_tab, [
                sale["date"], sale["address"], sale["price"],
                "", "", "New", sale["id"],
            ])
            # Canonical Lead_Log:
            # [Date, From, Email, Subject, Summary, Status, Chase Sent, Source]
            core.sheets_append_row(sheet_id, tab, [
                core.timestamp(),
                sale["address"],
                "",
                "Property sale — renovation lead",
                note,
                "Land Registry Lead",
                "",
                "",
            ])
            logged += 1
        except Exception as e:
            log.error(f"Could not log sale: {e}")

    # Build the weekly briefing
    total     = len(sales)
    premium   = sum(1 for s in sales if s["score"] >= 5)
    avg_price = sum(s["price"] for s in sales) / len(sales) if sales else 0

    lines = [
        f"Land Registry Radar — Week of {datetime.now().strftime('%d %B %Y')}",
        f"Postcode area: {prefix}",
        f"{'─'*50}",
        f"",
        f"Properties sold in your area this month: {total}",
        f"High renovation potential (score 5+/7): {premium}",
        f"Average sale price: {format_price(avg_price)}",
        f"Leads logged to your pipeline: {logged}",
        f"",
        f"Top 5 opportunities:",
        f"",
    ]

    type_names = {"D":"Detached","S":"Semi-detached","T":"Terraced","F":"Flat","O":"Other"}
    for s in sales[:5]:
        lines.append(f"  📍 {s['address']}")
        lines.append(f"     {type_names.get(s['type'], s['type'])} — {format_price(s['price'])}")
        lines.append(f"     Sold: {s['date']} — Contact from: {contact_date_from_sale(s['date'])}")
        lines.append(f"     Renovation score: {s['score']}/7")
        lines.append(f"")

    lines.append(f"{'─'*50}")
    lines.append(f"These {logged} properties have been added to your Lead_Log.")
    lines.append(f"Their owners are most likely planning renovation work in")
    lines.append(f"the next 1–6 months. First contact wins.")
    lines.append(f"")
    lines.append(f"Data source: HM Land Registry Price Paid Data")
    lines.append(f"Open Government Licence — updated monthly.")
    lines.append(f"")
    lines.append(f"Aether Frameworks — GAOS™ Land Registry Radar")

    core.gmail_send(
        gmail,
        cfg["gmail"]["alert_email"],
        cfg["gmail"]["watch_inbox"],
        f"GAOS Land Registry Radar — {total} sales, {premium} high-potential leads",
        "\n".join(lines)
    )
    log.info(f"Radar briefing sent. {total} sales scanned, {logged} leads logged.")
    return logged


def _tick(gmail, cfg):
    if core.should_run_at(RUN_HOUR, weekday=RUN_WEEKDAY):
        run_radar(gmail, cfg)


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info(f"Scheduled: every Monday at {RUN_HOUR}:00. Ctrl+C to stop.")
    core.run_loop(lambda: _tick(gmail, cfg),
                  cfg.get("settings", {}).get("check_every_seconds", 300))


if __name__ == "__main__":
    run()
