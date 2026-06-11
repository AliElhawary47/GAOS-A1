"""
GAOS™ MODULE 34 — Campaign Digest
Virtual Marketer | £199/mo bundle | Standalone: £650

Every Friday at 5pm, sends the owner a weekly marketing
performance digest: social posts published, reviews received,
newsletter sent, re-engagement emails sent, leads from chatbot.

A single email that tells the owner what their marketing did
this week — without them having to check four different places.

Target: Any business running the Virtual Marketer role.
Pain:   "I never know if our marketing is actually doing anything."
"""

from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("campaign_digest")

RUN_HOUR    = 17
RUN_WEEKDAY = 4   # Friday


def _in_last_days(value, days=7):
    """True when a sheet date cell parses and falls within the window.
    Unparseable cells never count — a name in a date column must not
    inflate the stats."""
    dt = core.parse_date(value)
    return bool(dt) and dt >= datetime.now() - timedelta(days=days)


def count_this_week(rows, date_col):
    """Count rows logged in the last 7 days."""
    return sum(1 for row in rows if _in_last_days(row.get(date_col, "")))


def count_reviews_by_sentiment(rows):
    """Returns (positive, negative, unrated) counts.
    Unknown star ratings are reported separately, never guessed."""
    pos = neg = unrated = 0
    for r in rows:
        stars = core.safe_int(r.get("Stars", ""), -1)
        if stars < 0:
            unrated += 1
        elif stars >= 4:
            pos += 1
        else:
            neg += 1
    return pos, neg, unrated


def generate_digest(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tabs     = cfg["google_sheets"]["tabs"]
    business = cfg["business"]["name"]
    today    = datetime.now().strftime("%d %B %Y")

    def read(tab_key, default):
        try:
            return core.sheets_read_all(sheet_id, tabs.get(tab_key, default))
        except Exception:
            return []

    # Gather data
    social_rows     = read("social_queue",     "Social_Queue")
    reviews_rows    = read("reviews_log",       "Reviews_Log")
    newsletter_rows = read("newsletter_queue",  "Newsletter_Queue")
    leads_rows      = read("leads",             "Lead_Log")
    reeng_rows      = read("clients",           "Clients")

    # Count this week's activity (canonical column names)
    social_sent     = sum(1 for r in social_rows
                          if str(r.get("Status","")).lower() == "sent"
                          and _in_last_days(r.get("Sent At","")))
    week_reviews    = [r for r in reviews_rows if _in_last_days(r.get("Date",""))]
    reviews_week    = len(week_reviews)
    pos_rev, neg_rev, unrated_rev = count_reviews_by_sentiment(week_reviews)
    newsletter_sent = sum(1 for r in newsletter_rows
                          if str(r.get("Status","")).lower() == "sent"
                          and str(r.get("Sent At",""))[:7] == datetime.now().strftime("%Y-%m"))
    chatbot_leads   = sum(1 for r in leads_rows
                          if "chatbot" in str(r.get("Status","")).lower()
                          and _in_last_days(r.get("Date","")))
    reeng_sent      = sum(1 for r in reeng_rows
                          if _in_last_days(r.get("Re-Engaged","")))

    # AI insight
    prompt = (
        f"Write a one-sentence marketing insight for {business} based on this week:\n"
        f"Social posts published: {social_sent}, Reviews: {reviews_week} "
        f"({pos_rev} positive, {neg_rev} negative, {unrated_rev} unrated), "
        f"Newsletter sent this month: {'Yes' if newsletter_sent else 'No'}, "
        f"Chatbot leads: {chatbot_leads}, Re-engagement emails: {reeng_sent}.\n"
        f"Be specific and actionable. Return ONLY the sentence."
    )
    insight = core.ask_deepseek(cfg["deepseek"]["api_key"], prompt,
                                max_tokens=80, expect_json=False)

    body = (
        f"Weekly Marketing Digest\n"
        f"Week ending {today}\n"
        f"{'─'*42}\n\n"
        f"📱 Social posts published:  {social_sent}\n"
        f"⭐ Reviews received:        {reviews_week} ({pos_rev}✓ {neg_rev}✗"
        f"{f' {unrated_rev}?' if unrated_rev else ''})\n"
        f"📧 Newsletter (this month): {'Sent' if newsletter_sent else 'Not sent yet'}\n"
        f"💬 Chatbot leads:           {chatbot_leads}\n"
        f"🔄 Re-engagement emails:    {reeng_sent}\n\n"
        f"{'─'*42}\n"
        f"This week: {insight or 'Keep the content consistent — consistency compounds.'}\n\n"
        f"Aether Frameworks — GAOS™ Campaign Digest"
    )

    core.gmail_send(
        gmail, cfg["gmail"]["alert_email"], cfg["gmail"]["watch_inbox"],
        f"GAOS Marketing Digest — week ending {today}", body
    )
    log.info("Campaign digest sent.")


def _tick(gmail, cfg):
    if core.should_run_at(RUN_HOUR, weekday=RUN_WEEKDAY):
        generate_digest(gmail, cfg)


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Scheduled: every Friday at 17:00. Ctrl+C to stop.")
    core.run_loop(lambda: _tick(gmail, cfg),
                  cfg.get("settings", {}).get("check_every_seconds", 300))


if __name__ == "__main__":
    run()
