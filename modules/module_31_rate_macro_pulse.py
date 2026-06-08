"""
GAOS™ MODULE 31 — Rate & Macro Pulse
Zone 0: Sense | Standalone: £700 | In: Enterprise

Watches two free macroeconomic signals and translates them into
specific, immediate actions for the business:

SIGNAL 1 — Bank of England Base Rate
Reads the Bank of England's published base rate daily.
When the rate changes, GAOS:
  - Alerts the owner immediately with a plain-English explanation
  - Drafts personalised outreach for all relevant clients
    (mortgage clients, finance clients, landlords)
  - Logs the rate change in the business record

The rate decision is published at noon on MPC decision days.
By 12:05 GAOS has read it. By 12:10 the owner has draft emails.
Their competitors find out when they open their email at 3pm.

SIGNAL 2 — ONS Consumer Price Index (CPI)
Reads the ONS CPI monthly. For every retainer client in the
Retainer_Clients sheet, calculates the real purchasing power
erosion since the contract was signed. When a contract has
silently lost 10% of its real value to inflation, GAOS flags it
with a suggested new rate and a draft price increase letter.

Both APIs are completely free:
  BoE IADB: https://www.bankofengland.co.uk/boeapps/database/
  ONS API:  https://api.beta.ons.gov.uk/v1/

No API keys. No rate limits. Open Government Licence.

Target: Mortgage brokers, financial advisors, estate agents,
        accountants, any business with retainer/recurring contracts.
Pain:   Rate changes create client demand spikes that businesses
        miss. Inflation silently erodes retainer contracts every month.
"""

import json
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("rate_macro_pulse")

CHECK_HOUR = 12   # Run at noon — BoE decisions published at 12:00
CPI_HOUR   = 8    # Monthly CPI check runs at 8am on 1st of month

# Bank of England IADB — base rate series
BOE_RATE_URL = ("https://www.bankofengland.co.uk/boeapps/database/_iadb-FromShowColumns.asp"
                "?csv.x=yes&Datefrom=01/{m}/{y}&Dateto=now&SeriesCodes=IUMABEDR&CSVF=TN&UsingCodes=Y")

# ONS CPI — CPIH series (headline CPI including housing costs)
ONS_CPI_URL = "https://api.beta.ons.gov.uk/v1/datasets/cpih01/editions/time-series/versions/20/observations?geography=K02000001&aggregate=cpih1dim1A0"

RATE_MEMORY_KEY = "boe_base_rate_last"
CPI_MEMORY_KEY  = "ons_cpi_last"

EROSION_ALERT_THRESHOLD = 0.08   # Alert when real value erosion exceeds 8%




# ── BANK OF ENGLAND RATE ──────────────────────────────────────

def fetch_current_boe_rate():
    """Fetches the current Bank of England base rate from the IADB."""
    import requests
    now   = datetime.now()
    url   = BOE_RATE_URL.format(m=f"{now.month:02d}", y=now.year)
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None
        # BoE CSV: Date, Rate — take last row
        lines = [l.strip() for l in r.text.split("\n") if l.strip()]
        data_lines = [l for l in lines if l and l[0].isdigit()]
        if not data_lines:
            return None
        last = data_lines[-1].split(",")
        return float(last[1].strip()) if len(last) >= 2 else None
    except Exception as e:
        log.error(f"BoE rate fetch error: {e}")
        return None


def get_stored_rate(cfg):
    """Retrieves the last recorded rate from GAOS memory."""
    try:
        from modules import module_25_gaos_learn as learn
        rows = core.sheets_read_all(
            cfg["google_sheets"]["sheet_id"], "GAOS_Memory"
        )
        for r in rows:
            if r.get("Key") == RATE_MEMORY_KEY:
                return float(r.get("Value", "0"))
    except Exception:
        pass
    return None


def store_rate(cfg, rate):
    """Stores the current rate in GAOS memory."""
    try:
        from modules import module_25_gaos_learn as learn
        learn.save_memory(cfg, RATE_MEMORY_KEY, str(rate))
    except Exception as e:
        log.error(f"Could not store rate: {e}")


def build_rate_change_prompt(old_rate, new_rate, business_name, business_type):
    direction = "cut" if new_rate < old_rate else "rise"
    change    = abs(new_rate - old_rate)
    return (
        f"The Bank of England has {direction} the base rate by {change:.2f}% "
        f"(from {old_rate:.2f}% to {new_rate:.2f}%). Write a short, warm email "
        f"from {business_name} ({business_type}) to a client explaining what this "
        f"means for them and inviting them to discuss. Max 80 words. Professional "
        f"but human tone. No jargon. Return ONLY the email body."
    )


def handle_rate_change(gmail, cfg, old_rate, new_rate):
    """Sends alerts and drafts client outreach when rate changes."""
    direction  = "CUT" if new_rate < old_rate else "RISE"
    change     = abs(new_rate - old_rate)
    business   = cfg["business"]["name"]
    biz_type   = cfg["business"].get("type", "financial services")

    log.warning(f"RATE CHANGE DETECTED: {old_rate:.2f}% → {new_rate:.2f}% ({direction})")

    # Alert the owner
    alert_body = (
        f"Bank of England Rate {direction}\n"
        f"{'─'*40}\n"
        f"Previous rate: {old_rate:.2f}%\n"
        f"New rate:      {new_rate:.2f}%\n"
        f"Change:        {'−' if new_rate < old_rate else '+'}{change:.2f}%\n\n"
        f"What to do now:\n"
        f"1. Review your clients who have variable-rate products\n"
        f"2. Use the draft email below to reach out today\n"
        f"3. Update your advice materials with the new rate\n\n"
        f"Draft client email is in your Drafts folder.\n\n"
        f"Aether Frameworks — GAOS™ Rate Pulse"
    )

    core.gmail_send(
        gmail,
        cfg["gmail"]["alert_email"],
        cfg["gmail"]["watch_inbox"],
        f"⚡ GAOS Rate Alert — BoE Rate {direction}: {old_rate:.2f}% → {new_rate:.2f}%",
        alert_body
    )

    # Draft outreach email for relevant clients
    draft_body = core.ask_deepseek(
        cfg["deepseek"]["api_key"],
        build_rate_change_prompt(old_rate, new_rate, business, biz_type),
        max_tokens=150,
        expect_json=False
    )

    if draft_body:
        # Save as a Gmail draft
        core.gmail_send(
            gmail,
            cfg["gmail"]["alert_email"],
            cfg["gmail"]["watch_inbox"],
            f"[DRAFT] Rate change: what this means for you — {business}",
            f"DRAFT EMAIL — Personalise and send to relevant clients:\n\n{draft_body}"
        )
        log.info("Draft rate change email saved.")


# ── ONS CPI CONTRACT EROSION ──────────────────────────────────

def fetch_current_cpi():
    """Fetches the latest ONS CPIH headline rate."""
    import requests
    # Alternative: use the simpler ONS time series endpoint
    url = "https://api.beta.ons.gov.uk/v1/datasets/cpih01/editions/time-series/versions/20/observations"
    try:
        r = requests.get(url, timeout=15, params={
            "geography":  "K02000001",
            "aggregate":  "cpih1dim1A0",
        })
        if r.status_code != 200:
            # Fallback: fetch the published CPI page
            return _fetch_cpi_fallback()
        data = r.json()
        obs  = data.get("observations", [])
        if obs:
            # Take the most recent non-null value
            recent = sorted(
                (o for o in obs if o.get("observation") not in (None, "")),
                key=lambda x: x.get("time", ""),
                reverse=True
            )
            if recent:
                return float(str(recent[0]["observation"]).replace(",", ""))
        return _fetch_cpi_fallback()
    except Exception as e:
        log.error(f"ONS CPI fetch error: {e}")
        return _fetch_cpi_fallback()


def _fetch_cpi_fallback():
    """Fetches CPI from the Bank of England IADB as a fallback."""
    import requests
    now = datetime.now()
    url = ("https://www.bankofengland.co.uk/boeapps/database/_iadb-FromShowColumns.asp"
           f"?csv.x=yes&Datefrom=01/01/{now.year - 1}&Dateto=now"
           "&SeriesCodes=CPIRATE&CSVF=TN&UsingCodes=Y")
    try:
        r = requests.get(url, timeout=15)
        lines = [l.strip() for l in r.text.split("\n") if l.strip()]
        data  = [l for l in lines if l and l[0].isdigit()]
        if data:
            last = data[-1].split(",")
            return float(last[1].strip()) if len(last) >= 2 else None
    except Exception:
        pass
    return None


def calculate_erosion(start_date_str, current_cpi, base_cpi=None):
    """
    Estimates contract value erosion since signing date.
    Uses CPI as a proxy for inflation since contract signed.
    Returns erosion as a fraction (e.g. 0.083 = 8.3% erosion).
    """
    if not current_cpi:
        return 0.0
    try:
        start_dt = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
        months   = (datetime.now() - start_dt).days / 30.44
        # Estimate annual CPI rate from current published value
        # CPI is published as a year-on-year % change
        annual_rate = current_cpi / 100
        erosion = 1 - (1 / (1 + annual_rate)) ** (months / 12)
        return round(max(0, erosion), 4)
    except Exception:
        return 0.0


def run_cpi_check(gmail, cfg, cpi_rate):
    """
    Checks every retainer contract against current CPI.
    Flags contracts where real value has eroded beyond threshold.
    """
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("retainer_clients", "Retainer_Clients")
    business = cfg["business"]["name"]

    try:
        rows = core.sheets_read_all(sheet_id, tab)
    except Exception as e:
        log.error(f"Could not read retainer clients: {e}")
        return

    erosion_flags = []
    for row in rows:
        active        = str(row.get("Active", "yes")).strip().lower()
        client        = str(row.get("Client Name", "")).strip()
        fee_str       = str(row.get("Monthly Fee", "0")).strip()
        currency      = str(row.get("Currency", "£")).strip()
        last_invoiced = str(row.get("Last Invoiced", "")).strip()

        if active not in ("yes", "true", "1", "y") or not client:
            continue

        # Use Last Invoiced as proxy for contract start if no start date
        contract_date = last_invoiced or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        try:
            fee = float(str(fee_str).replace(",", "").replace("£", ""))
        except ValueError:
            continue

        erosion  = calculate_erosion(contract_date, cpi_rate)
        if erosion < EROSION_ALERT_THRESHOLD:
            continue

        inflation_adj_fee = round(fee * (1 + erosion), 2)
        monthly_loss      = round(inflation_adj_fee - fee, 2)
        annual_loss       = round(monthly_loss * 12, 2)

        erosion_flags.append({
            "client":      client,
            "current_fee": fee,
            "adj_fee":     inflation_adj_fee,
            "currency":    currency,
            "erosion_pct": round(erosion * 100, 1),
            "monthly_loss":monthly_loss,
            "annual_loss": annual_loss,
            "since":       contract_date,
        })

    if not erosion_flags:
        log.info(f"CPI check complete. Current CPI: {cpi_rate}%. No contracts flagged.")
        return

    # Build the erosion report
    total_annual_loss = sum(f["annual_loss"] for f in erosion_flags)
    lines = [
        f"Contract Value Erosion Report",
        f"Date: {datetime.now().strftime('%d %B %Y')}",
        f"Current CPI Rate: {cpi_rate}%",
        f"{'─'*50}",
        f"",
        f"{len(erosion_flags)} contract(s) flagged for review:",
        f"Estimated total annual undercharging: {erosion_flags[0]['currency']}{total_annual_loss:,.0f}",
        f"",
    ]

    for f in erosion_flags:
        lines.append(f"  Client:          {f['client']}")
        lines.append(f"  Current fee:     {f['currency']}{f['current_fee']:.0f}/month")
        lines.append(f"  Inflation-adj:   {f['currency']}{f['adj_fee']:.0f}/month")
        lines.append(f"  Erosion:         {f['erosion_pct']}%")
        lines.append(f"  You're losing:   {f['currency']}{f['annual_loss']:.0f}/year")
        lines.append(f"  Contract since:  {f['since']}")
        lines.append(f"")

    lines.append("─"*50)
    lines.append("Suggested action: raise fees at next contract renewal.")
    lines.append("A template price increase letter is below.")
    lines.append("")
    lines.append("— PRICE INCREASE LETTER TEMPLATE —")
    lines.append("")
    lines.append(f"Dear [Client Name],")
    lines.append(f"")
    lines.append(f"I hope you are well. I am writing to let you know that, in line with")
    lines.append(f"current inflation, we will be adjusting our fees from [DATE].")
    lines.append(f"")
    lines.append(f"Your new monthly fee will be [AMOUNT], reflecting an increase of")
    lines.append(f"approximately [X]% in line with the Consumer Price Index.")
    lines.append(f"")
    lines.append(f"We value our relationship enormously and remain committed to")
    lines.append(f"delivering the same high standard of service.")
    lines.append(f"")
    lines.append(f"Please do not hesitate to get in touch if you have any questions.")
    lines.append(f"")
    lines.append(f"Best regards,")
    lines.append(f"{business}")
    lines.append("")
    lines.append("Aether Frameworks — GAOS™ Rate & Macro Pulse")

    core.gmail_send(
        gmail,
        cfg["gmail"]["alert_email"],
        cfg["gmail"]["watch_inbox"],
        f"GAOS Macro Pulse — {len(erosion_flags)} contract(s) underpriced vs. inflation",
        "\n".join(lines)
    )
    log.info(f"CPI erosion report sent. {len(erosion_flags)} contracts flagged. "
             f"Estimated annual loss: £{total_annual_loss:,.0f}")


# ── RUN ──────────────────────────────────────────────────────

def _tick(gmail, cfg):
    if core.should_run_at(CHECK_HOUR):
        current_rate = fetch_current_boe_rate()
        if current_rate is not None:
            stored_rate = get_stored_rate(cfg)
            if stored_rate is None:
                log.info(f"Base rate recorded for first time: {current_rate:.2f}%")
                store_rate(cfg, current_rate)
            elif abs(current_rate - stored_rate) >= 0.01:
                handle_rate_change(gmail, cfg, stored_rate, current_rate)
                store_rate(cfg, current_rate)
            else:
                log.info(f"Rate unchanged: {current_rate:.2f}%")

    if core.should_run_at(CPI_HOUR, day_of_month=1):
        cpi = fetch_current_cpi()
        if cpi:
            log.info(f"ONS CPI: {cpi}% — checking contract erosion...")
            run_cpi_check(gmail, cfg, cpi)
        else:
            log.warning("Could not fetch ONS CPI data.")


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Watching Bank of England rate (noon daily) and ONS CPI (1st of month). Ctrl+C to stop.")
    core.run_loop(lambda: _tick(gmail, cfg), cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
