"""
GAOS™ MODULE 35 — AI Chief of Staff
Included in: Full Team | Standalone: £1,200/mo

The central nervous system of the business.

Every morning at 07:30, reads every active virtual role's data sources,
scores and prioritises all intelligence items, and delivers one
plain-English briefing — via email and WhatsApp.

Also handles natural language queries on WhatsApp:
  "What needs my attention today?"
  "Who owes me money?"
  "Who should I call today?"
  "What's coming up this week?"
  "How many leads this week?"

Role-aware: only surfaces intelligence from the client's active
subscriptions. A Finance + Sales client gets a different briefing
than a Full Team client. Integrates with GAOS Learn for context.

The difference between a system that does things and one that
thinks with you.

Runs: Daily at 07:30 (email + WhatsApp briefing)
      On-demand via WhatsApp (any time)
      Weekly strategic summary: Mondays at 07:45

Integration with Module 23 (WhatsApp Agent):
  m23 calls handle_if_cos_query() before standard FAQ handling.
  If the message matches a CoS pattern, CoS handles it → returns True.
  m23 then skips its standard reply.
"""

import re
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional
import gaos_core as core

log = core.get_logger("chief_of_staff")

BRIEF_HOUR    = 7
BRIEF_MINUTE  = 30
WEEKLY_MINUTE = 45   # Monday 07:45 strategic summary

# ── DATA MODEL ───────────────────────────────────────────────

@dataclass
class IntelItem:
    """A single piece of actionable intelligence."""
    category:  str          # "urgent" | "warm" | "watch" | "good" | "info"
    role:      str          # which virtual role produced this
    headline:  str          # one-line plain English
    detail:    str          # extra context (used by AI for briefing)
    score:     float        # priority score (higher = more urgent)
    action:    str = ""     # suggested action for the owner

# ── ROLE → DATA SOURCE MAPPING ───────────────────────────────

ROLE_SOURCES = {
    "finance":      ["invoices", "revenue_snapshot"],
    "sales":        ["leads", "proposals"],
    "admin":        ["sentinel_actions", "pending_documents"],
    "receptionist": ["appointments"],
    "marketer":     ["reviews_log", "newsletter_queue"],
    "intelligence": ["gaos_memory", "planning_leads", "gazette_log"],
}

# Natural language query patterns for WhatsApp routing
COS_QUERY_PATTERNS = [
    r"what('s| is) (my |the )?(top |daily )?priorit",
    r"what needs? (my )?attention",
    r"what should i (do|focus|work on|call|chase)",
    r"who (owes|should i call|is at risk|hasn't paid)",
    r"how many (leads|invoices|calls|appointments|reviews)",
    r"what'?s? (coming up|due|overdue|outstanding|urgent)",
    r"(show|give|tell) me (my |the )?(briefing|summary|digest|report|status)",
    r"(morning|daily|weekly) (brief|update|report|summary)",
    r"(any |new )?(leads|invoices|messages|alerts|opportunities)",
    r"chief of staff",
    r"what did gaos (do|find|catch|notice)",
    r"(revenue|income|money|cash) (this week|today|this month)",
]

COS_PATTERN = re.compile("|".join(COS_QUERY_PATTERNS), re.IGNORECASE)


def is_cos_query(text: str) -> bool:
    return bool(COS_PATTERN.search(text.strip()))


def is_run_time(weekly=False):
    now = datetime.now()
    if now.hour != BRIEF_HOUR:
        return False
    if weekly:
        return now.weekday() == 0 and now.minute >= BRIEF_MINUTE + 10 and now.minute < BRIEF_MINUTE + 15
    return now.minute >= BRIEF_MINUTE and now.minute < BRIEF_MINUTE + 5


# ── INTELLIGENCE GATHERERS ────────────────────────────────────

def gather_finance(cfg) -> List[IntelItem]:
    items = []
    try:
        sheet_id = cfg["google_sheets"]["sheet_id"]
        tab      = cfg["google_sheets"]["tabs"].get("invoices", "Invoice_Log")
        rows     = core.sheets_read_all(sheet_id, tab)
        today    = datetime.now()

        for row in rows:
            status  = str(row.get("Status", "")).strip().lower()
            vendor  = str(row.get("Vendor", row.get("Client", ""))).strip()
            amount  = str(row.get("Amount", "")).strip()
            due_str = str(row.get("Invoice Date", row.get("InvoiceDate", row.get("Date", "")))).strip()

            if status in ("paid", "cancelled", "void"):
                continue

            days_overdue = 0
            if due_str:
                try:
                    due_dt = datetime.strptime(due_str[:10], "%Y-%m-%d")
                    days_overdue = (today - due_dt).days
                except ValueError:
                    pass

            if days_overdue >= 30:
                items.append(IntelItem(
                    category="urgent",
                    role="finance",
                    headline=f"{vendor} invoice {amount} — {days_overdue} days overdue",
                    detail=f"Outstanding invoice from {vendor} for {amount}. {days_overdue} days past due date.",
                    score=80 + min(days_overdue, 40),
                    action=f"Call {vendor} today or escalate to a final notice."
                ))
            elif days_overdue >= 14:
                items.append(IntelItem(
                    category="warm",
                    role="finance",
                    headline=f"{vendor} invoice {amount} — {days_overdue} days outstanding",
                    detail=f"Invoice from {vendor} for {amount} is {days_overdue} days past due.",
                    score=50 + days_overdue,
                    action="Payment Chaser will send a reminder today."
                ))
    except Exception as e:
        log.error(f"gather_finance error: {e}")
    return items


def gather_sales(cfg) -> List[IntelItem]:
    items = []
    try:
        sheet_id = cfg["google_sheets"]["sheet_id"]
        today    = datetime.now()
        week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")

        # New leads
        lead_tab = cfg["google_sheets"]["tabs"].get("leads", "Lead_Log")
        leads    = core.sheets_read_all(sheet_id, lead_tab)
        new_leads  = [r for r in leads
                      if str(r.get("Logged At", ""))[:10] >= week_ago
                      and str(r.get("Status","")).lower() not in ("won","lost")]
        hot_leads  = [r for r in new_leads
                      if "urgent" in str(r.get("Status","")).lower()
                      or "hot"    in str(r.get("Status","")).lower()]

        if hot_leads:
            for lead in hot_leads[:3]:
                name = str(lead.get("Name", lead.get("Company","Lead"))).strip()
                items.append(IntelItem(
                    category="urgent",
                    role="sales",
                    headline=f"Hot lead: {name} — needs a response today",
                    detail=f"Urgent enquiry from {name} in your lead log.",
                    score=90,
                    action=f"Review and send the draft reply to {name}."
                ))
        elif new_leads:
            items.append(IntelItem(
                category="warm",
                role="sales",
                headline=f"{len(new_leads)} new lead(s) this week",
                detail=f"{len(new_leads)} enquiries received. Draft replies are in your Gmail drafts.",
                score=45,
                action="Review and send draft replies from Gmail."
            ))

        # Unanswered proposals
        prop_tab  = cfg["google_sheets"]["tabs"].get("proposals", "Proposals")
        proposals = core.sheets_read_all(sheet_id, prop_tab)
        cold_props = []
        for p in proposals:
            status   = str(p.get("Status","")).lower()
            sent_str = str(p.get("Proposal Date", p.get("Sent At", p.get("Date","")))).strip()
            if status in ("won","lost","declined"):
                continue
            if sent_str:
                try:
                    sent_dt    = datetime.strptime(sent_str[:10], "%Y-%m-%d")
                    days_since = (today - sent_dt).days
                    if days_since >= 10:
                        cold_props.append((days_since, p))
                except ValueError:
                    pass

        for days, prop in sorted(cold_props, reverse=True)[:2]:
            client = str(prop.get("Client", prop.get("Name",""))).strip()
            value  = str(prop.get("Value", prop.get("Amount",""))).strip()
            items.append(IntelItem(
                category="warm",
                role="sales",
                headline=f"{client} hasn't responded to your proposal — {days} days",
                detail=f"Proposal sent to {client} {value and f'for {value}' or ''} {days} days ago. No response.",
                score=40 + days,
                action="Proposal Chaser will follow up automatically."
            ))
    except Exception as e:
        log.error(f"gather_sales error: {e}")
    return items


def gather_admin(cfg) -> List[IntelItem]:
    items = []
    try:
        sheet_id  = cfg["google_sheets"]["sheet_id"]
        sentinel  = cfg["google_sheets"]["tabs"].get("sentinel_actions", "Sentinel_Actions")
        today_str = datetime.now().strftime("%Y-%m-%d")
        week_str  = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        rows = core.sheets_read_all(sheet_id, sentinel)
        for row in rows:
            status    = str(row.get("Status","open")).lower()
            obligation = str(row.get("Obligation","")).strip()
            deadline  = str(row.get("Deadline Date","")).strip()
            priority  = str(row.get("Priority","normal")).lower()

            if status == "done" or not obligation:
                continue

            if priority == "urgent" or (deadline and deadline <= week_str):
                score = 95 if deadline and deadline <= today_str else 75
                items.append(IntelItem(
                    category="urgent",
                    role="admin",
                    headline=f"Document obligation: {obligation[:60]}",
                    detail=f"Document Sentinel flagged: {obligation}. Deadline: {deadline or 'unspecified'}.",
                    score=score,
                    action="Check your Sentinel_Actions sheet for the source document."
                ))
    except Exception as e:
        log.error(f"gather_admin error: {e}")
    return items


def gather_receptionist(cfg) -> List[IntelItem]:
    items = []
    try:
        sheet_id = cfg["google_sheets"]["sheet_id"]
        tab      = cfg["google_sheets"]["tabs"].get("appointments","Appointments")
        today    = datetime.now()
        tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        rows     = core.sheets_read_all(sheet_id, tab)

        upcoming = [r for r in rows
                    if str(r.get("Date",""))[:10] == tomorrow
                    and str(r.get("Status","")).lower() not in ("cancelled","no-show")]
        if upcoming:
            items.append(IntelItem(
                category="info",
                role="receptionist",
                headline=f"{len(upcoming)} appointment(s) tomorrow",
                detail=f"{len(upcoming)} bookings scheduled for tomorrow. Reminders sent automatically.",
                score=20,
                action=""
            ))

        missed = [r for r in rows
                  if str(r.get("Date",""))[:10] == today.strftime("%Y-%m-%d")
                  and str(r.get("Status","")).lower() == "no-show"]
        for r in missed:
            name = str(r.get("Client Name", r.get("Client", r.get("Name","")))).strip()
            items.append(IntelItem(
                category="warm",
                role="receptionist",
                headline=f"No-show: {name} — rebooking message sent",
                detail=f"{name} missed their appointment today. Rebooking message sent automatically.",
                score=30,
                action=""
            ))
    except Exception as e:
        log.error(f"gather_receptionist error: {e}")
    return items


def gather_intelligence(cfg) -> List[IntelItem]:
    items = []
    try:
        sheet_id = cfg["google_sheets"]["sheet_id"]

        # At-risk clients from GAOS memory
        try:
            mem_rows = core.sheets_read_all(sheet_id, "GAOS_Memory")
            for row in mem_rows:
                if str(row.get("Key","")) == "at_risk_clients":
                    clients = str(row.get("Value","")).strip()
                    if clients:
                        items.append(IntelItem(
                            category="watch",
                            role="intelligence",
                            headline=f"Client Pulse: relationship cooling detected",
                            detail=f"Clients flagged by Client Pulse: {clients}",
                            score=55,
                            action="Review the Monday Client Pulse report and reach out personally."
                        ))
                    break
        except Exception:
            pass

        # Planning / Land Registry leads added this week (modules 28+30 write to Lead_Log)
        try:
            lead_tab = cfg["google_sheets"]["tabs"].get("leads", "Lead_Log")
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            lead_rows = core.sheets_read_all(sheet_id, lead_tab)
            new_leads = [r for r in lead_rows
                         if str(r.get("Logged At",""))[:10] >= week_ago
                         and str(r.get("Status","")).lower() in ("planning lead","land registry lead")]
            if new_leads:
                items.append(IntelItem(
                    category="info",
                    role="intelligence",
                    headline=f"{len(new_leads)} new planning/land lead(s) this week",
                    detail=f"Planning Radar and Land Registry Radar found {len(new_leads)} new opportunities.",
                    score=25,
                    action="Review Lead_Log sheet (filter by Status = Planning Lead) for addresses."
                ))
        except Exception:
            pass

        # Good news: positive reviews
        try:
            rev_tab  = cfg["google_sheets"]["tabs"].get("reviews_log","Reviews_Log")
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            rev_rows = core.sheets_read_all(sheet_id, rev_tab)
            pos_revs = [r for r in rev_rows
                        if str(r.get("Date",""))[:10] >= week_ago
                        and str(r.get("Stars","0")).strip().isdigit()
                        and int(str(r.get("Stars","0")).strip()) >= 4]
            if pos_revs:
                items.append(IntelItem(
                    category="good",
                    role="intelligence",
                    headline=f"{len(pos_revs)} positive review(s) this week",
                    detail=f"{len(pos_revs)} new 4–5 star reviews. Draft responses in your Reviews_Log.",
                    score=10,
                    action="Post the draft responses to Google Business Profile."
                ))
        except Exception:
            pass

    except Exception as e:
        log.error(f"gather_intelligence error: {e}")
    return items


def gather_marketer(cfg) -> List[IntelItem]:
    items = []
    try:
        sheet_id = cfg["google_sheets"]["sheet_id"]
        nl_tab   = cfg["google_sheets"]["tabs"].get("newsletter_queue","Newsletter_Queue")
        month    = datetime.now().strftime("%Y-%m")
        nl_rows  = core.sheets_read_all(sheet_id, nl_tab)
        pending  = [r for r in nl_rows
                    if str(r.get("Status","")).lower() not in ("sent","skip")
                    and str(r.get("Month",""))[:7] == month]
        if pending and datetime.now().day > 5:
            items.append(IntelItem(
                category="watch",
                role="marketer",
                headline="Monthly newsletter not yet sent",
                detail="Newsletter for this month has bullet points queued but hasn't been sent yet.",
                score=35,
                action="Add your topics to the Newsletter_Queue sheet and the mailer runs next Monday."
            ))
    except Exception as e:
        log.error(f"gather_marketer error: {e}")
    return items


# ── AGGREGATOR ───────────────────────────────────────────────

GATHERERS = {
    "finance":      gather_finance,
    "sales":        gather_sales,
    "admin":        gather_admin,
    "receptionist": gather_receptionist,
    "intelligence": gather_intelligence,
    "marketer":     gather_marketer,
}


def gather_all_intelligence(cfg) -> List[IntelItem]:
    """
    Reads all active roles' data sources and returns a combined,
    prioritised list of intelligence items.
    """
    active_roles = cfg.get("active_roles", list(GATHERERS.keys()))
    all_items    = []

    for role in active_roles:
        if role in GATHERERS:
            role_items = GATHERERS[role](cfg)
            all_items.extend(role_items)
            if role_items:
                log.info(f"  {role}: {len(role_items)} item(s)")

    # Sort: urgent first, then by score descending
    order = {"urgent": 0, "warm": 1, "watch": 2, "info": 3, "good": 4}
    all_items.sort(key=lambda x: (order.get(x.category, 5), -x.score))
    return all_items


# ── BRIEFING BUILDER ─────────────────────────────────────────

def build_briefing_prompt(items, owner_name, business_name, day_str):
    sections = {}
    for item in items:
        sections.setdefault(item.category, []).append(item)

    summary_parts = []
    for category, label in [("urgent","URGENT"),("warm","WARM"),("watch","WATCH"),("good","GOOD NEWS")]:
        cat_items = sections.get(category, [])
        if cat_items:
            part = f"{label}:\n" + "\n".join(
                f"- {i.headline} | {i.detail}" for i in cat_items[:4]
            )
            summary_parts.append(part)

    if not summary_parts:
        return None

    data_summary = "\n\n".join(summary_parts)
    return (
        f"You are GAOS Chief of Staff for {business_name}.\n"
        f"Write a morning briefing for {owner_name} on {day_str}.\n\n"
        f"Data from all active systems:\n{data_summary}\n\n"
        f"Format the briefing as:\n"
        f"Good morning, {owner_name}.\n\n"
        f"[today's date, friendly]\n\n"
        f"── URGENT (needs you today) ─────────\n"
        f"[bullet each urgent item, with specific numbers and names]\n\n"
        f"── WARM (worth attention this week) ──\n"
        f"[bullet each warm item]\n\n"
        f"── WATCHING ─────────────────────────\n"
        f"[bullet each watch item]\n\n"
        f"── GOOD NEWS ────────────────────────\n"
        f"[bullet good news items]\n\n"
        f"── YOUR TEAM IS RUNNING ─────────────\n"
        f"[One sentence: what GAOS automated overnight that the owner didn't have to do]\n\n"
        f"Reply with any question and I'll answer from your live data.\n"
        f"── GAOS Chief of Staff\n\n"
        f"Rules: Use specific names, amounts, and numbers. No vague statements. "
        f"If no urgent items, say so clearly. Be direct and human — not corporate. "
        f"Under 280 words total. Return ONLY the briefing text."
    )


def build_briefing(items, cfg) -> str:
    """Uses AI to write the prioritised morning briefing."""
    owner    = cfg["business"].get("owner_name", "there")
    business = cfg["business"]["name"]
    day_str  = datetime.now().strftime("%A, %d %B")

    if not items:
        return (
            f"Good morning, {owner}.\n\n"
            f"{day_str}\n\n"
            f"No urgent items in your active systems.\n\n"
            f"Your virtual team is running. Reply with any question.\n"
            f"── GAOS Chief of Staff"
        )

    prompt = build_briefing_prompt(items, owner, business, day_str)
    if not prompt:
        return f"Good morning, {owner}. All systems running normally. No items requiring your attention today."

    briefing = core.ask_deepseek(
        cfg["deepseek"]["api_key"],
        prompt,
        max_tokens=400,
        expect_json=False
    )
    return briefing or f"Good morning, {owner}. Your systems are running. Reply 'briefing' for a full status."


# ── QUERY HANDLER ─────────────────────────────────────────────

def build_query_response_prompt(query, items, cfg):
    owner    = cfg["business"].get("owner_name", "")
    business = cfg["business"]["name"]
    data     = "\n".join(f"- [{i.category.upper()}] {i.headline} | {i.detail}" for i in items[:12])
    return (
        f"You are GAOS Chief of Staff for {business}. "
        f"The owner {owner} just asked via WhatsApp: '{query}'\n\n"
        f"Current intelligence from all active systems:\n{data}\n\n"
        f"Answer the question directly using only the data above. "
        f"Be specific — use names, numbers, amounts. "
        f"If the data doesn't contain the answer, say so honestly. "
        f"Keep it under 80 words. No preamble. Return ONLY the answer."
    )


def handle_if_cos_query(gmail, cfg, message_text: str, sender_number: str) -> bool:
    """
    Called by Module 23 (WhatsApp Agent) before its standard handling.
    Returns True if this was a CoS query (and we handled it).
    Returns False if Module 23 should proceed normally.
    """
    if not is_cos_query(message_text):
        return False

    log.info(f"CoS query from {sender_number}: {message_text[:60]}")
    try:
        items    = gather_all_intelligence(cfg)
        prompt   = build_query_response_prompt(message_text, items, cfg)
        response = core.ask_deepseek(
            cfg["deepseek"]["api_key"], prompt,
            max_tokens=150, expect_json=False
        )
        if response:
            tw = cfg["twilio"]
            core.send_whatsapp(
                tw["account_sid"], tw["auth_token"],
                tw.get("whatsapp_from", f"whatsapp:{tw['from_number']}"), sender_number,
                response
            )
            return True
    except Exception as e:
        log.error(f"CoS query handling failed: {e}")
    return False


# ── DAILY BRIEFING ────────────────────────────────────────────

def run_morning_brief(gmail, cfg):
    """Sends the daily morning briefing via email and WhatsApp."""
    log.info("Chief of Staff: gathering intelligence...")
    items    = gather_all_intelligence(cfg)
    briefing = build_briefing(items, cfg)

    urgent_count = sum(1 for i in items if i.category == "urgent")
    subject = (
        f"⚡ {urgent_count} urgent item(s) need your attention"
        if urgent_count
        else f"✓ GAOS Morning Brief — {datetime.now().strftime('%A %d %B')}"
    )

    # Email briefing
    core.gmail_send(
        gmail,
        cfg["gmail"]["alert_email"],
        cfg["gmail"]["watch_inbox"],
        subject,
        briefing
    )

    # WhatsApp briefing (if Twilio configured)
    try:
        tw = cfg["twilio"]
        if "YOUR_" not in str(tw.get("account_sid","")):
            core.send_whatsapp(
                tw["account_sid"], tw["auth_token"],
                tw.get("whatsapp_from", f"whatsapp:{tw['from_number']}"),
                f"whatsapp:{tw['owner_mobile']}",
                briefing[:1500]   # WhatsApp message limit
            )
    except Exception as e:
        log.warning(f"WhatsApp briefing failed (email sent OK): {e}")

    log.info(f"Morning brief sent. {len(items)} items ({urgent_count} urgent).")
    return len(items), urgent_count


# ── WEEKLY STRATEGIC SUMMARY ──────────────────────────────────

def run_weekly_summary(gmail, cfg):
    """
    Monday 07:45 — a slightly different format.
    Looks back at the week and forward at the coming week.
    """
    items    = gather_all_intelligence(cfg)
    owner    = cfg["business"].get("owner_name","there")
    business = cfg["business"]["name"]

    total    = len(items)
    urgent   = sum(1 for i in items if i.category == "urgent")
    good     = sum(1 for i in items if i.category == "good")

    data_str = "\n".join(f"- [{i.category.upper()}] {i.headline}" for i in items[:15])

    prompt = (
        f"You are GAOS Chief of Staff for {business}.\n"
        f"Write a weekly strategic summary for {owner} on Monday morning.\n\n"
        f"Current state across all systems:\n{data_str}\n\n"
        f"Format:\n"
        f"Good morning, {owner}. Here's your week ahead.\n\n"
        f"── THIS WEEK'S PRIORITIES ───────────\n"
        f"[Top 3 items needing the owner's personal attention this week]\n\n"
        f"── YOUR VIRTUAL TEAM THIS WEEK ─────\n"
        f"[What GAOS will handle automatically — be specific]\n\n"
        f"── WATCH ────────────────────────────\n"
        f"[Anything building that needs awareness but not action yet]\n\n"
        f"Be direct. Use names and numbers. Under 200 words. "
        f"Return ONLY the summary text."
    )

    summary = core.ask_deepseek(
        cfg["deepseek"]["api_key"], prompt,
        max_tokens=300, expect_json=False
    )

    if summary:
        core.gmail_send(
            gmail,
            cfg["gmail"]["alert_email"],
            cfg["gmail"]["watch_inbox"],
            f"GAOS Weekly Brief — week of {datetime.now().strftime('%d %B')}",
            summary
        )
        log.info("Weekly strategic summary sent.")


# ── ENGINE INTERFACE ──────────────────────────────────────────

def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 35 — AI Chief of Staff")
    print("="*60 + "\n")
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Scheduled: daily 07:30, weekly Mondays 07:45. Ctrl+C to stop.\n")

    while True:
        try:
            if is_run_time():
                run_morning_brief(gmail, cfg)
            if is_run_time(weekly=True):
                run_weekly_summary(gmail, cfg)
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Chief of Staff error: {ex}")
        time.sleep(300)


if __name__ == "__main__":
    run()
