"""
╔══════════════════════════════════════════════════════════════╗
║   GAOS™ MODULE 25 — GAOS Learn                              ║
║   Adaptive Business Memory                                  ║
║                                                             ║
║   Standalone: £500 add-on | Auto-included: Enterprise       ║
║                                                             ║
║   GAOS Learn watches your data week by week and builds a    ║
║   living memory of how this specific business operates.     ║
║   That memory is then injected into every AI call, making   ║
║   GAOS smarter, more accurate, and more personal over time. ║
║                                                             ║
║   What it learns:                                           ║
║   • Average invoice value and normal vendor range           ║
║   • Busiest days for leads and typical enquiry types        ║
║   • Conversion rate from lead to contract                   ║
║   • Revenue trend and week-on-week patterns                 ║
║   • Clients who reliably pay late                           ║
║   • Most common FAQ questions                               ║
║                                                             ║
║   What changes as a result:                                 ║
║   • Invoice anomaly detection (flags unusual amounts)       ║
║   • Lead scoring (prioritises most likely to convert)       ║
║   • Personalised daily digests referencing real trends      ║
║   • Smarter payment chase timing per client                 ║
╚══════════════════════════════════════════════════════════════╝

Runs as a scheduled weekly process (every Monday at 7am, before the
Daily Digest fires at 8am so the digest gets the fresh context).

Memory is stored in a single "GAOS_Memory" sheet tab as key-value rows.
All other modules call gaos_learn.get_context() to inject it into prompts.
"""

import time
import re
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("gaos_learn")

MEMORY_TAB   = "GAOS_Memory"
UPDATE_HOUR  = 7
UPDATE_WKDAY = 0    # Monday


# ══════════════════════════════════════════════════════════════
#  MEMORY READ / WRITE
# ══════════════════════════════════════════════════════════════

def get_context(cfg):
    """
    Returns a plain-English context string to inject into AI prompts.
    Called by other modules before each AI call.

    Returns empty string if no memory exists yet (first week).
    """
    try:
        rows = core.sheets_read_all(cfg["google_sheets"]["sheet_id"], MEMORY_TAB)
        if not rows:
            return ""
        memory = {r.get("Key",""): r.get("Value","") for r in rows}
        lines = [v for v in memory.values() if v]
        return "Business context:\n" + "\n".join(f"- {l}" for l in lines) if lines else ""
    except Exception:
        return ""


def save_memory(cfg, key, value):
    """Upserts a key-value row in the GAOS_Memory tab."""
    sheet_id = cfg["google_sheets"]["sheet_id"]
    try:
        rows = core.sheets_read_all(sheet_id, MEMORY_TAB)
        for i, r in enumerate(rows):
            if r.get("Key") == key:
                core.sheets_update_cell(sheet_id, MEMORY_TAB, i + 2, 2, value)
                return
        core.sheets_append_row(sheet_id, MEMORY_TAB, [key, value, core.timestamp()])
    except Exception as e:
        log.error(f"Memory save failed for '{key}': {e}")


# ══════════════════════════════════════════════════════════════
#  LEARNING FUNCTIONS
# ══════════════════════════════════════════════════════════════

def _parse_amount(s):
    try:
        return float(re.sub(r"[^\d.]", "", str(s)))
    except Exception:
        return 0.0


def learn_invoices(cfg):
    """Learns average invoice value, common vendors, and late payers."""
    tab  = cfg["google_sheets"]["tabs"].get("invoices", "Invoice_Log")
    rows = core.sheets_read_all(cfg["google_sheets"]["sheet_id"], tab)
    if len(rows) < 5:
        return

    amounts   = [_parse_amount(r.get("Amount", 0)) for r in rows if _parse_amount(r.get("Amount",0)) > 0]
    vendors   = [str(r.get("Vendor","")).strip() for r in rows if r.get("Vendor")]
    late_rows = [r for r in rows if str(r.get("Chase Sent","")).lower() == "sent"]

    if amounts:
        avg = sum(amounts) / len(amounts)
        mx  = max(amounts)
        mn  = min(amounts)
        save_memory(cfg, "invoice_avg",
                    f"Average invoice value is £{avg:.0f} (range £{mn:.0f}–£{mx:.0f}). "
                    f"Flag any invoice over £{avg*2.5:.0f} as unusually high.")

    if vendors:
        from collections import Counter
        top = Counter(vendors).most_common(3)
        save_memory(cfg, "top_vendors",
                    f"Most common suppliers: {', '.join(v for v,_ in top)}.")

    if late_rows:
        late_names = list({str(r.get("Vendor","")).strip() for r in late_rows})[:3]
        save_memory(cfg, "late_payers",
                    f"Suppliers with previous late payment chases: {', '.join(late_names)}. "
                    f"Consider earlier reminder timing for these.")

    log.info(f"Invoice memory updated ({len(rows)} invoices analysed)")


def learn_leads(cfg):
    """Learns lead volume trends, busiest days, and conversion signals."""
    tab  = cfg["google_sheets"]["tabs"].get("leads", "Lead_Log")
    rows = core.sheets_read_all(cfg["google_sheets"]["sheet_id"], tab)
    if len(rows) < 5:
        return

    from collections import Counter

    # Day-of-week distribution
    day_counts = Counter()
    for r in rows:
        try:
            dt = datetime.strptime(str(r.get("Logged At",""))[:10], "%Y-%m-%d")
            day_counts[dt.strftime("%A")] += 1
        except Exception:
            pass

    if day_counts:
        busiest = day_counts.most_common(1)[0][0]
        save_memory(cfg, "busiest_lead_day",
                    f"Most leads arrive on {busiest}s. Prioritise fast replies on that day.")

    # Conversion rate
    won  = sum(1 for r in rows if str(r.get("Status","")).lower() in ("won","converted","closed-won"))
    rate = round(won / len(rows) * 100) if rows else 0
    save_memory(cfg, "lead_conversion",
                f"Lead conversion rate: {rate}% ({won} won from {len(rows)} total leads).")

    log.info(f"Lead memory updated ({len(rows)} leads analysed, {rate}% conversion)")


def learn_revenue(cfg):
    """Learns weekly revenue trend and seasonal patterns."""
    tab  = cfg["google_sheets"]["tabs"].get("invoices", "Invoice_Log")
    rows = core.sheets_read_all(cfg["google_sheets"]["sheet_id"], tab)
    if len(rows) < 10:
        return

    # Last 4 weeks totals
    weekly = {}
    for r in rows:
        try:
            dt   = datetime.strptime(str(r.get("Logged At",""))[:10], "%Y-%m-%d")
            wkey = dt.strftime("%Y-W%W")
            weekly[wkey] = weekly.get(wkey, 0) + _parse_amount(r.get("Amount", 0))
        except Exception:
            pass

    if len(weekly) >= 2:
        weeks  = sorted(weekly.keys())[-4:]
        totals = [weekly[w] for w in weeks]
        avg4w  = sum(totals) / len(totals)
        save_memory(cfg, "revenue_trend",
                    f"4-week average weekly revenue: £{avg4w:.0f}. "
                    f"Use this baseline when commenting on weekly snapshots.")

    log.info("Revenue memory updated")


def learn_faqs(cfg):
    """Learns which FAQ questions come up most and what's missing."""
    tab  = cfg["google_sheets"]["tabs"].get("faq", "FAQ_Knowledge_Base")
    rows = core.sheets_read_all(cfg["google_sheets"]["sheet_id"], tab)
    if not rows:
        return

    count = len(rows)
    save_memory(cfg, "faq_count",
                f"The FAQ knowledge base has {count} question-answer pairs. "
                f"When a question is unanswered, flag it for the owner to add.")

    log.info(f"FAQ memory updated ({count} entries)")


def learn_appointments(cfg):
    """Learns no-show rate and appointment volume patterns."""
    tab  = cfg["google_sheets"]["tabs"].get("appointments", "Appointments")
    rows = core.sheets_read_all(cfg["google_sheets"]["sheet_id"], tab)
    if len(rows) < 5:
        return

    total    = len(rows)
    noshows  = sum(1 for r in rows if str(r.get("Status","")).lower() == "no-show")
    ns_rate  = round(noshows / total * 100) if total else 0

    if ns_rate > 0:
        save_memory(cfg, "noshow_rate",
                    f"No-show rate: {ns_rate}% ({noshows} of {total} appointments). "
                    f"{'High — consider requiring deposits.' if ns_rate > 15 else 'Within normal range.'}")

    log.info(f"Appointment memory updated ({total} appointments, {ns_rate}% no-show rate)")


# ══════════════════════════════════════════════════════════════
#  CONTEXT INJECTION HELPERS (used by other modules)
# ══════════════════════════════════════════════════════════════

def inject(cfg, base_prompt):
    """
    Wraps any AI prompt with the current business context memory.

    Usage in other modules:
        from modules import module_25_gaos_learn as learn
        enriched = learn.inject(cfg, my_prompt)
        result   = core.ask_deepseek(api_key, enriched)

    If no memory exists yet, returns the base_prompt unchanged.
    """
    context = get_context(cfg)
    if not context:
        return base_prompt
    return f"{context}\n\n{base_prompt}"


def inject_chat(cfg, system_prompt):
    """
    Wraps a system prompt (for chat_deepseek) with business context.
    Used by Modules 22, 23, 24.
    """
    context = get_context(cfg)
    if not context:
        return system_prompt
    return f"{system_prompt}\n\n{context}"


# ══════════════════════════════════════════════════════════════
#  WEEKLY LEARNING CYCLE
# ══════════════════════════════════════════════════════════════

def is_learn_time():
    now = datetime.now()
    return now.weekday() == UPDATE_WKDAY and now.hour == UPDATE_HOUR and now.minute < 5


def run_learning_cycle(cfg):
    """Runs all learning functions and updates the memory tab."""
    log.info("Running weekly learning cycle...")

    ensure_memory_tab(cfg)
    learn_invoices(cfg)
    learn_leads(cfg)
    learn_revenue(cfg)
    learn_faqs(cfg)
    learn_appointments(cfg)

    save_memory(cfg, "last_updated",
                f"GAOS memory last updated: {datetime.now().strftime('%A %d %B %Y at %H:%M')}")
    log.info("Learning cycle complete. Memory updated.\n")


def ensure_memory_tab(cfg):
    """Creates the GAOS_Memory tab if it doesn't exist."""
    sheet_id = cfg["google_sheets"]["sheet_id"]
    try:
        core.sheets_read_all(sheet_id, MEMORY_TAB)
    except Exception:
        try:
            import gspread
            gc          = gspread.service_account(filename="google_credentials.json")
            spreadsheet = gc.open_by_key(sheet_id)
            tab         = spreadsheet.add_worksheet(title=MEMORY_TAB, rows=50, cols=3)
            tab.append_row(["Key", "Value", "Updated At"])
            log.info(f"Created {MEMORY_TAB} tab")
        except Exception as e:
            log.error(f"Could not create memory tab: {e}")


# ══════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════

def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 25 - GAOS Learn (Adaptive Memory)")
    print("="*60 + "\n")
    cfg = core.load_config()
    log.info(f"Scheduled: every Monday at {UPDATE_HOUR}:00am. Ctrl+C to stop.\n")

    while True:
        try:
            if is_learn_time():
                run_learning_cycle(cfg)
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Learning cycle error: {ex}")
        time.sleep(300)


if __name__ == "__main__":
    run()
