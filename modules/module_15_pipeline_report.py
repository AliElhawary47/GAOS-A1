"""
GAOS™ MODULE 15 — Lead Pipeline Report
Zone 3: Report | Standalone: £750 | In: GAOS™ Pro, Enterprise

Every Friday at 5pm, reads the Lead_Log sheet and emails the owner a
clear pipeline summary — open leads, response rate, oldest uncontacted
lead, and conversion count. Helps the owner know where the money is.

Target client: Estate agents, consultants, agencies, any sales-driven business.
Pain solved:   Not knowing which leads are going cold or how the pipeline is performing.
"""

from datetime import datetime, timedelta
import gaos_core as core

log = core.get_logger("pipeline_report")

REPORT_HOUR    = 17
REPORT_WEEKDAY = 4   # Friday = 4


def days_since(date_str):
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return (datetime.now() - dt).days
    except Exception:
        return 0


def generate_pipeline_report(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("leads", "Lead_Log")
    rows     = core.sheets_read_all(sheet_id, tab)

    if not rows:
        log.info("No leads in pipeline.")
        return

    total       = len(rows)
    open_leads  = [r for r in rows if str(r.get("Status","")).lower() not in ("closed","won","lost")]
    won         = [r for r in rows if str(r.get("Status","")).lower() in ("won","converted","closed-won")]
    no_reply    = [r for r in open_leads if str(r.get("Status","")).lower() in ("","new","draft ready")]

    oldest_days = max((days_since(str(r.get("Logged At",""))) for r in open_leads), default=0)

    prompt = (
        f"Write a concise Friday pipeline summary for {cfg['business']['name']}.\n"
        f"Data: Total leads: {total}, Open: {len(open_leads)}, Won: {len(won)}, "
        f"Awaiting reply: {len(no_reply)}, Oldest open lead: {oldest_days} days old.\n"
        f"Keep it under 100 words, professional and actionable. Return ONLY the text."
    )

    insight = core.ask_deepseek(cfg["deepseek"]["api_key"], prompt,
                                max_tokens=150, expect_json=False)
    if not insight:
        insight = f"Pipeline has {len(open_leads)} open leads. {len(no_reply)} awaiting reply."

    body = (
        f"Lead Pipeline Report — {datetime.now().strftime('%d %B %Y')}\n"
        f"{'─'*40}\n\n"
        f"Total Leads:         {total}\n"
        f"Open / Active:       {len(open_leads)}\n"
        f"Won / Converted:     {len(won)}\n"
        f"Awaiting Reply:      {len(no_reply)}\n"
        f"Oldest Open Lead:    {oldest_days} days\n\n"
        f"{'─'*40}\n"
        f"Weekly Insight:\n{insight}\n\n"
        f"Aether Frameworks — GAOS™ Pipeline Report"
    )

    core.gmail_send(
        gmail, cfg["gmail"]["alert_email"], cfg["gmail"]["watch_inbox"],
        f"GAOS Pipeline Report — {datetime.now().strftime('%d %b %Y')}", body
    )
    log.info(f"Pipeline report sent. {len(open_leads)} open leads.")


def _maybe_run(gmail, cfg):
    if core.should_run_at(REPORT_HOUR, weekday=REPORT_WEEKDAY):
        generate_pipeline_report(gmail, cfg)


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("module_15_pipeline_report: Scheduled every Friday at 5pm.")
    core.run_loop(lambda: _maybe_run(gmail, cfg), 300)


if __name__ == "__main__":
    run()
