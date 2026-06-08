"""
╔══════════════════════════════════════════════════════════════╗
║   GAOS™ MODULE 07 — Centralised Team Notification HQ        ║
║   Standalone: £900  |  In: GAOS™ Enterprise                 ║
╠══════════════════════════════════════════════════════════════╣
║   Watches key business events (new payment emails, new      ║
║   signed clients, big leads) and broadcasts a clean         ║
║   notification into a single Slack channel so the whole     ║
║   team has one shared source of truth in real time.         ║
║                                                             ║
║   Target client:  Growing teams of 10-30 across departments ║
║   Pain solved:    Scattered data, "did X happen?" confusion ║
╚══════════════════════════════════════════════════════════════╝

This module turns email-based business events into Slack posts.
It looks for trigger emails (e.g. Stripe receipts, signed
contracts) and posts a formatted summary to #company-updates.
"""

import time
import gaos_core as core

log = core.get_logger("team_broadcaster")


# Define the events GAOS watches for and how to label them in Slack.
# Each trigger maps a Gmail search to a Slack message style.
EVENT_TRIGGERS = [
    {
        "name":  "payment",
        "query": 'is:unread (from:stripe.com OR subject:"payment received" OR subject:"you have been paid")',
        "emoji": "💰",
        "title": "Payment Received",
    },
    {
        "name":  "new_client",
        "query": 'is:unread (subject:"contract signed" OR subject:"agreement accepted")',
        "emoji": "🎉",
        "title": "New Client Signed",
    },
    {
        "name":  "big_lead",
        "query": 'is:unread (subject:quote OR subject:"large enquiry")',
        "emoji": "🔔",
        "title": "New Lead",
    },
]


def summarise_for_slack(cfg, event_title, email_text):
    """Uses AI to turn a raw email into a one-line Slack update."""
    prompt = f"""Summarise this business event email in ONE short, upbeat line
suitable for a team Slack channel. Event type: {event_title}.

Return ONLY valid JSON with one key:
  Summary  — a single line, max 20 words, no names of internal staff.

Email:
---
{email_text[:1200]}
---
ONLY JSON. No markdown."""

    data = core.ask_deepseek(cfg["deepseek"]["api_key"], prompt, max_tokens=80)
    if data and data.get("Summary"):
        return data["Summary"]
    return f"{event_title} — check inbox for details."


def process_events(gmail, cfg):
    """Checks all trigger types and posts any new events to Slack."""
    webhook = cfg["slack"]["webhook_url"]
    posted  = 0

    for trigger in EVENT_TRIGGERS:
        emails = core.gmail_search(gmail, trigger["query"])

        for e in emails:
            _, msg    = core.gmail_get_message(gmail, e["id"])
            body_text = core.gmail_get_body_text(msg)

            summary = summarise_for_slack(cfg, trigger["title"], body_text)
            message = f"{trigger['emoji']} *{trigger['title']}*\n{summary}\n_{core.timestamp()}_"

            if "YOUR_" in webhook:
                log.warning(f"Slack not configured — would post: {message}")
            else:
                if core.post_to_slack(webhook, message):
                    log.info(f"Posted to Slack: {trigger['title']}")
                    posted += 1

            core.gmail_mark_read(gmail, e["id"])

    return posted


def run():
    print("\n" + "="*60)
    print("  GAOS MODULE 07 - Centralised Team Notification HQ")
    print("="*60 + "\n")

    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("Watching for business events to broadcast. Ctrl+C to stop.\n")

    total = 0
    while True:
        try:
            n = process_events(gmail, cfg)
            total += n
            if n:
                log.info(f"Broadcast {n} event(s). {total} total.\n")
            else:
                log.info(f"No new events. Next check in {cfg['settings']['check_every_seconds']//60} min.")
        except KeyboardInterrupt:
            print("\nStopped.\n"); break
        except Exception as ex:
            log.error(f"Loop error: {ex}")
        time.sleep(cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
