"""
GAOS™ MODULE 18 — Social Post Scheduler
Zone 4: Schedule | Standalone: £900 | In: GAOS™ Enterprise

Reads a Social_Queue sheet where the owner (or their team) drops
raw content ideas. At the scheduled time, GAOS uses AI to write a
polished post with hashtags, then emails it ready to copy-paste, and
optionally posts via a configured webhook (e.g. Buffer, Make, Zapier).

Sheet tab required: Social_Queue
Columns: Platform | Raw Idea | Scheduled Date | Status | Post Draft | Sent At

Target client: Any business that needs consistent social presence.
Pain solved:   Social media paralysis — ideas sitting unposted because nobody has time to write them.
"""

from datetime import datetime
import gaos_core as core

log = core.get_logger("social_scheduler")

STATUS_COL    = 4   # "Status"
DRAFT_COL     = 5   # "Post Draft"
SENT_AT_COL   = 6   # "Sent At"


def build_post_prompt(platform, raw_idea, business_name):
    platform_notes = {
        "linkedin": "professional tone, no more than 3 hashtags, include a call to action",
        "instagram": "casual and visual tone, 5-8 relevant hashtags, emoji welcome",
        "facebook": "friendly community tone, 1-2 hashtags, conversational",
        "twitter": "punchy, under 200 characters, 1-2 hashtags",
    }.get(platform.lower(), "professional and engaging, 2-3 hashtags")

    return (
        f"Write a social media post for {business_name} on {platform}.\n"
        f"Style: {platform_notes}\n"
        f"Raw idea from the team: {raw_idea}\n\n"
        f"Return ONLY the finished post text. No explanation. No quotes around it."
    )


def process_due_posts(gmail, cfg):
    sheet_id = cfg["google_sheets"]["sheet_id"]
    tab      = cfg["google_sheets"]["tabs"].get("social_queue", "Social_Queue")
    rows     = core.sheets_read_all(sheet_id, tab)
    today    = datetime.now().strftime("%Y-%m-%d")
    sent     = 0

    for i, row in enumerate(rows):
        status    = str(row.get("Status",         "")).strip().lower()
        scheduled = str(row.get("Scheduled Date", "")).strip()[:10]
        platform  = str(row.get("Platform",       "general")).strip()
        raw_idea  = str(row.get("Raw Idea",       "")).strip()

        if status in ("sent", "cancelled") or scheduled > today or not raw_idea:
            continue

        log.info(f"Generating {platform} post for: {raw_idea[:50]}...")

        # Generate post using AI
        post_text = core.ask_deepseek(
            cfg["deepseek"]["api_key"],
            build_post_prompt(platform, raw_idea, cfg["business"]["name"]),
            max_tokens=200,
            expect_json=False
        )

        if not post_text:
            post_text = raw_idea   # fallback: use raw idea as-is

        # Email the ready-to-post content to the owner
        body = (
            f"Your scheduled {platform.title()} post is ready:\n\n"
            f"{'─'*40}\n"
            f"{post_text}\n"
            f"{'─'*40}\n\n"
            f"Copy and paste this into {platform.title()} to post it.\n\n"
            f"Aether Frameworks — GAOS™ Social Scheduler"
        )
        core.gmail_send(
            gmail, cfg["gmail"]["alert_email"], cfg["gmail"]["watch_inbox"],
            f"Your {platform.title()} post is ready — {today}", body
        )

        # Update sheet
        core.sheets_update_cell(sheet_id, tab, i + 2, DRAFT_COL, post_text)
        core.sheets_update_cell(sheet_id, tab, i + 2, STATUS_COL, "Sent")
        core.sheets_update_cell(sheet_id, tab, i + 2, SENT_AT_COL, core.timestamp())
        sent += 1

    return sent


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("module_18_social_scheduler: Watching Social_Queue for scheduled posts.")
    core.run_loop(lambda: process_due_posts(gmail, cfg),
                  cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
