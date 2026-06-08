"""
GAOS™ MODULE 26 — Client Pulse
Zone 6: Learn | Add-on: £600 | Auto-included: Enterprise

The Silence Radar. Reads Gmail thread history per known client
and detects relationship cooling — declining response frequency,
shortening messages, widening reply gaps — before the client
has consciously decided to leave.

Delivers a weekly Relationship Health report ranked by risk.
Feeds directly into the Re-Engagement Mailer with priority scoring.

No new APIs. No new infrastructure. Just the Gmail data already
flowing through the system, read backwards in time.

Runs every Monday at 07:30 — before the Daily Digest at 08:00,
so the digest can reference relationship health if needed.

Target: Any service business with recurring client relationships.
Pain solved: The client who goes quiet and disappears. Silently.
             While you were busy. And you didn't notice until they
             had already decided to leave.
"""

import re
from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("client_pulse")

RUN_HOUR   = 7
RUN_MINUTE = 30
RUN_WKDAY  = 0   # Monday

WARM_THRESHOLD  = 0.7   # above = green
COOL_THRESHOLD  = 0.4   # below = red (at risk)




# ── GMAIL THREAD ANALYSIS ────────────────────────────────────

def get_recent_threads(gmail, client_email, days=60):
    """Returns last N days of Gmail threads with a given client email."""
    try:
        cutoff = int((datetime.now() - timedelta(days=days)).timestamp())
        results = gmail.users().messages().list(
            userId="me",
            q=f"from:{client_email} OR to:{client_email} after:{cutoff}",
            maxResults=40
        ).execute()
        return results.get("messages", [])
    except Exception as e:
        log.error(f"Thread fetch failed for {client_email}: {e}")
        return []


def analyse_thread_patterns(gmail, client_email, days=60):
    """
    Analyses response patterns for a client email address.
    Returns a dict of communication health indicators.
    """
    messages = get_recent_threads(gmail, client_email, days)
    if not messages:
        return None

    msg_details = []
    for m in messages[:20]:   # cap at 20 to avoid rate limits
        try:
            detail = gmail.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From","Date","Subject"]
            ).execute()
            headers = {h["name"]: h["value"]
                       for h in detail.get("payload", {}).get("headers", [])}
            internal_date = int(detail.get("internalDate", 0)) / 1000
            snippet = detail.get("snippet", "")
            from_addr = headers.get("From", "")
            msg_details.append({
                "ts":      internal_date,
                "from_me": client_email not in from_addr,
                "len":     len(snippet),
                "date":    datetime.fromtimestamp(internal_date)
            })
        except Exception:
            continue

    if len(msg_details) < 2:
        return None

    msg_details.sort(key=lambda x: x["ts"])

    # Split into recent half and older half for comparison
    mid   = len(msg_details) // 2
    older = msg_details[:mid]
    newer = msg_details[mid:]

    def avg_len(msgs):
        client_msgs = [m for m in msgs if not m["from_me"]]
        return sum(m["len"] for m in client_msgs) / len(client_msgs) if client_msgs else 0

    def avg_gap(msgs):
        """Average days between their messages."""
        their_msgs = sorted([m for m in msgs if not m["from_me"]], key=lambda x: x["ts"])
        if len(their_msgs) < 2:
            return None
        gaps = [(their_msgs[i+1]["ts"] - their_msgs[i]["ts"]) / 86400
                for i in range(len(their_msgs)-1)]
        return sum(gaps) / len(gaps) if gaps else None

    older_len  = avg_len(older)
    newer_len  = avg_len(newer)
    older_gap  = avg_gap(older)
    newer_gap  = avg_gap(newer)

    last_from_client = max(
        (m["date"] for m in msg_details if not m["from_me"]),
        default=None
    )
    days_since = (datetime.now() - last_from_client).days if last_from_client else 999

    # Health score: 0 (very cold) → 1 (very warm)
    score = 1.0

    # Length shrinking? Penalise
    if older_len > 0 and newer_len < older_len * 0.6:
        score -= 0.25

    # Gap widening? Penalise
    if older_gap and newer_gap and newer_gap > older_gap * 1.8:
        score -= 0.25

    # Long silence? Penalise
    if days_since > 30:
        score -= 0.25
    if days_since > 60:
        score -= 0.25

    score = max(0.0, min(1.0, score))

    return {
        "email":       client_email,
        "score":       score,
        "days_since":  days_since,
        "len_trend":   "shrinking" if newer_len < older_len * 0.7 else "stable",
        "gap_trend":   "widening"  if (older_gap and newer_gap and newer_gap > older_gap * 1.5) else "stable",
        "msg_count":   len(msg_details),
    }


def classify(score):
    if score >= WARM_THRESHOLD:
        return "Warm", "✓"
    if score >= COOL_THRESHOLD:
        return "Cooling", "⚠"
    return "At Risk", "✗"


def build_insight(data):
    """Returns a plain-English sentence about what the data shows."""
    issues = []
    if data["days_since"] > 60:
        issues.append(f"no message in {data['days_since']} days")
    elif data["days_since"] > 30:
        issues.append(f"last message {data['days_since']} days ago")
    if data["len_trend"] == "shrinking":
        issues.append("messages getting shorter")
    if data["gap_trend"] == "widening":
        issues.append("taking longer to reply")
    if not issues:
        return "Communication pattern looks healthy."
    return f"Signs of cooling: {'; '.join(issues)}."


# ── REPORT ───────────────────────────────────────────────────

def run_pulse_check(gmail, cfg):
    """
    Reads known clients from the Clients sheet, analyses each one's
    Gmail thread patterns, and emails a ranked relationship health report.
    """
    sheet_id  = cfg["google_sheets"]["sheet_id"]
    tab       = cfg["google_sheets"]["tabs"].get("clients", "Clients")
    rows      = core.sheets_read_all(sheet_id, tab)
    business  = cfg["business"]["name"]
    today_str = datetime.now().strftime("%A %d %B %Y")

    if not rows:
        log.info("No clients in sheet — skipping pulse check.")
        return

    results = []
    for row in rows:
        name  = str(row.get("Name",  "")).strip()
        email = str(row.get("Email", "")).strip()
        if not email or not name:
            continue

        log.info(f"Checking pulse: {name} ({email})")
        data = analyse_thread_patterns(gmail, email)
        if data:
            data["name"] = name
            results.append(data)

    if not results:
        log.info("No communication data found for any clients.")
        return

    # Sort: most at-risk first
    results.sort(key=lambda x: x["score"])

    # Build report
    lines = [
        f"Client Relationship Health Report",
        f"Week of {today_str}",
        f"Business: {business}",
        f"{'─'*50}",
        "",
    ]

    at_risk  = [r for r in results if r["score"] < COOL_THRESHOLD]
    cooling  = [r for r in results if COOL_THRESHOLD <= r["score"] < WARM_THRESHOLD]
    warm     = [r for r in results if r["score"] >= WARM_THRESHOLD]

    if at_risk:
        lines.append("AT RISK — Act this week:")
        for r in at_risk:
            status, icon = classify(r["score"])
            lines.append(f"  {icon} {r['name']} ({r['email']})")
            lines.append(f"     {build_insight(r)}")
        lines.append("")

    if cooling:
        lines.append("COOLING — Worth a check-in:")
        for r in cooling:
            status, icon = classify(r["score"])
            lines.append(f"  {icon} {r['name']} ({r['email']})")
            lines.append(f"     {build_insight(r)}")
        lines.append("")

    if warm:
        lines.append(f"WARM ({len(warm)} clients) — All healthy.")
        for r in warm:
            lines.append(f"  ✓ {r['name']}")
        lines.append("")

    lines.append("─"*50)
    lines.append("Tip: Reply to 'At Risk' clients personally today.")
    lines.append("GAOS will send automated re-engagement in 7 days")
    lines.append("if no response is logged.")
    lines.append("")
    lines.append("Aether Frameworks — GAOS™ Client Pulse")

    body = "\n".join(lines)
    subject = f"GAOS Client Pulse — {len(at_risk)} at risk, {len(cooling)} cooling"

    core.gmail_send(
        gmail,
        cfg["gmail"]["alert_email"],
        cfg["gmail"]["watch_inbox"],
        subject, body
    )
    log.info(f"Pulse report sent. At risk: {len(at_risk)}, "
             f"cooling: {len(cooling)}, warm: {len(warm)}")

    # Feed at-risk clients into GAOS_Learn memory for Re-Engagement priority
    if at_risk:
        try:
            from modules import module_25_gaos_learn as learn
            at_risk_names = ", ".join(r["name"] for r in at_risk)
            learn.save_memory(cfg, "at_risk_clients",
                              f"Clients currently at churn risk: {at_risk_names}. "
                              f"Prioritise personal outreach before automated messages.")
            log.info("At-risk clients written to GAOS memory.")
        except Exception as e:
            log.error(f"Could not write to GAOS memory: {e}")


# ── RUN ──────────────────────────────────────────────────────

def _tick(gmail, cfg):
    if core.should_run_at(RUN_HOUR, weekday=RUN_WKDAY, minute_start=RUN_MINUTE):
        run_pulse_check(gmail, cfg)


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info(f"Scheduled: every Monday at {RUN_HOUR}:{RUN_MINUTE:02d}. Ctrl+C to stop.")
    core.run_loop(lambda: _tick(gmail, cfg), cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
