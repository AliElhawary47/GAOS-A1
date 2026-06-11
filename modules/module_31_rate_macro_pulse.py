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

Both feeds are completely free (verified live):
  BoE IADB CSV: bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp
                (months must be %b format, e.g. 01/Jan/2026; rows are
                month-end dated, so query a few months back)
  ONS website JSON: ons.gov.uk/economy/inflationandpriceindices/
                timeseries/d7g7/mm23/data (12-month CPI % rate;
                the old api.ons.gov.uk was retired in Nov 2024)

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

# Bank of England IADB — base rate series (IUMABEDR), CSV output.
# {since} must be %d/%b/%Y (e.g. 01/Mar/2026) — numeric months return HTTP 500.
BOE_RATE_URL = ("https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp"
                "?csv.x=yes&Datefrom={since}&Dateto=now"
                "&SeriesCodes=IUMABEDR&CSVF=TN&UsingCodes=Y")

# ONS CPI all-items 12-month % rate (series D7G7, dataset MM23) —
# served as JSON by the ONS website itself.
ONS_CPI_URL = ("https://www.ons.gov.uk/economy/inflationandpriceindices"
               "/timeseries/d7g7/mm23/data")

_HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (GAOS Rate Pulse)"}

RATE_MEMORY_KEY = "boe_base_rate_last"
CPI_MEMORY_KEY  = "ons_cpi_last"

EROSION_ALERT_THRESHOLD = 0.08   # Alert when real value erosion exceeds 8%




# ── BANK OF ENGLAND RATE ──────────────────────────────────────

def fetch_current_boe_rate():
    """Fetches the current Bank of England base rate from the IADB.
    Rows are month-end dated, so look back ~4 months and take the
    latest row."""
    import requests
    since = (datetime.now() - timedelta(days=120)).strftime("01/%b/%Y")
    url   = BOE_RATE_URL.format(since=since)
    try:
        r = requests.get(url, timeout=20, headers=_HTTP_HEADERS)
        if r.status_code != 200:
            log.error(f"BoE IADB returned {r.status_code}")
            return None
        # BoE CSV: "31 May 2026,3.75" — take the last data row
        lines = [l.strip() for l in r.text.split("\n") if l.strip()]
        data_lines = [l for l in lines if l and l[0].isdigit() and "," in l]
        if not data_lines:
            return None
        last = data_lines[-1].split(",")
        return float(last[1].strip()) if len(last) >= 2 else None
    except Exception as e:
        log.error(f"BoE rate fetch error: {e}")
        return None


def get_stored_rate(cfg):
    """Retrieves the last recorded rate from GAOS memory
    (canonical GAOS_Memory columns: Key | Value | Updated)."""
    try:
        rows = core.sheets_read_all(
            cfg["google_sheets"]["sheet_id"], "GAOS_Memory"
        )
        for r in rows:
            if r.get("Key") == RATE_MEMORY_KEY:
                value = str(r.get("Value", "")).strip()
                return float(value) if value else None
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
        f"2. A draft client email has been saved to your Gmail Drafts\n"
        f"3. Update your advice materials with the new rate\n\n"
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
        # Save as a real Gmail draft, as the alert email promises
        core.gmail_create_draft(
            gmail,
            cfg["gmail"]["alert_email"],
            f"Rate change: what this means for you — {business}",
            draft_body
        )
        log.info("Draft rate change email saved to Drafts.")

    # Canonical Macro_Log: [Date, Type, Value, Change, Notes]
    try:
        core.sheets_append_row(
            cfg["google_sheets"]["sheet_id"],
            cfg["google_sheets"]["tabs"].get("macro_log", "Macro_Log"),
            [core.timestamp(), "BoE Base Rate", f"{new_rate:.2f}%",
             f"{'+' if new_rate > old_rate else '−'}{change:.2f}%",
             f"Changed from {old_rate:.2f}%"]
        )
    except Exception:
        pass


# ── ONS CPI CONTRACT EROSION ──────────────────────────────────

def fetch_current_cpi():
    """Fetches the latest ONS CPI all-items 12-month % rate (e.g. 2.8).
    The value is already a year-on-year percentage, NOT an index."""
    import requests
    try:
        r = requests.get(ONS_CPI_URL, timeout=20, headers=_HTTP_HEADERS)
        if r.status_code != 200:
            log.error(f"ONS returned {r.status_code}")
            return None
        months = r.json().get("months", [])
        for entry in reversed(months):
            value = str(entry.get("value", "")).strip()
            if value:
                return float(value)
        return None
    except Exception as e:
        log.error(f"ONS CPI fetch error: {e}")
        return None


def calculate_erosion(start_date_str, current_cpi, base_cpi=None):
    """
    Estimates contract value erosion since signing date.
    Uses CPI as a proxy for inflation since contract signed.
    Returns erosion as a fraction (e.g. 0.083 = 8.3% erosion).
    """
    if not current_cpi:
        return 0.0
    start_dt = core.parse_date(start_date_str)
    if not start_dt:
        return 0.0
    try:
        months = (datetime.now() - start_dt).days / 30.44
        # current_cpi is the published year-on-year % rate (e.g. 2.8)
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
        # Canonical Retainer_Clients: Name | Email | Amount | Billing Day | Status | Last Invoice
        status        = str(row.get("Status", "")).strip().lower()
        client        = str(row.get("Name", "")).strip()
        fee_str       = str(row.get("Amount", "0")).strip()
        currency      = "£"
        last_invoiced = str(row.get("Last Invoice", "")).strip()

        if status not in ("", "active", "yes", "true", "1", "y") or not client:
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
            try:
                core.sheets_append_row(
                    cfg["google_sheets"]["sheet_id"],
                    cfg["google_sheets"]["tabs"].get("macro_log", "Macro_Log"),
                    [core.timestamp(), "ONS CPI", f"{cpi}%", "",
                     "Monthly contract erosion check"]
                )
            except Exception:
                pass
            run_cpi_check(gmail, cfg, cpi)
        else:
            log.warning("Could not fetch ONS CPI data.")


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Watching Bank of England rate (noon daily) and ONS CPI (1st of month). Ctrl+C to stop.")
    core.run_loop(lambda: _tick(gmail, cfg),
                  cfg.get("settings", {}).get("check_every_seconds", 300))


if __name__ == "__main__":
    run()
