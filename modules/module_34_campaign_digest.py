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


def count_this_week(rows, date_col, default_col=None):
    """Count rows logged in the current week."""
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    count = 0
    for row in rows:
        date_str = str(row.get(date_col, "") or row.get(default_col or "", ""))[:10]
        if date_str >= week_start:
            count += 1
    return count


def count_reviews_by_sentiment(rows):
    pos = sum(1 for r in rows
              if str(r.get("Stars","0")).strip().isdigit()
              and int(str(r.get("Stars","0")).strip()) >= 4)
    neg = len(rows) - pos
    return pos, neg


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

    # Count this week's activity
    social_sent     = sum(1 for r in social_rows
                          if str(r.get("Status","")).lower() == "sent"
                          and str(r.get("Sent At",""))[:10] >=
                          (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"))
    reviews_week    = count_this_week(reviews_rows, "Date", "Logged At")
    pos_rev, neg_rev = count_reviews_by_sentiment(reviews_rows[-reviews_week:]) if reviews_week else (0, 0)
    newsletter_sent = sum(1 for r in newsletter_rows
                          if str(r.get("Status","")).lower() == "sent"
                          and str(r.get("Sent At",""))[:7] == datetime.now().strftime("%Y-%m"))
    chatbot_leads   = sum(1 for r in leads_rows
                          if "chatbot" in str(r.get("Status","")).lower()
                          and str(r.get("Logged At",""))[:10] >=
                          (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"))
    reeng_sent      = sum(1 for r in reeng_rows
                          if str(r.get("Re-Engaged",""))[:10] >=
                          (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"))

    # AI insight
    prompt = (
        f"Write a one-sentence marketing insight for {business} based on this week:\n"
        f"Social posts published: {social_sent}, Reviews: {reviews_week} "
        f"({pos_rev} positive, {neg_rev} negative), "
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
        f"⭐ Reviews received:        {reviews_week} ({pos_rev}✓ {neg_rev}✗)\n"
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
    core.run_loop(lambda: _tick(gmail, cfg), cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
