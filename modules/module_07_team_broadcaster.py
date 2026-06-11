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

import re
import gaos_core as core

log = core.get_logger("team_broadcaster")

_AMOUNT_RE = re.compile(r'[£$€]\s*[\d,]+(?:\.\d{2})?')


GAOS_BROADCAST_LABEL = "GAOS-Broadcast"


# Define the events GAOS watches for and how to label them in Slack.
# Each trigger maps a Gmail search to a Slack message style.
# "mark_read" — whether this trigger may also mark the email read after a
# successful post. big_lead must NOT: module 03 still needs the unread
# "quote" email to fire its SMS alert; the label alone stops reprocessing.
EVENT_TRIGGERS = [
    {
        "name":  "payment",
        "query": 'is:unread -label:gaos-broadcast (from:stripe.com OR subject:"payment received" OR subject:"you have been paid")',
        "emoji": "💰",
        "title": "Payment Received",
        "mark_read": True,
    },
    {
        "name":  "new_client",
        "query": 'is:unread -label:gaos-broadcast (subject:"contract signed" OR subject:"agreement accepted")',
        "emoji": "🎉",
        "title": "New Client Signed",
        "mark_read": True,
    },
    {
        "name":  "big_lead",
        "query": 'is:unread -label:gaos-broadcast (subject:quote OR subject:"large enquiry")',
        "emoji": "🔔",
        "title": "New Lead",
        "mark_read": False,
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

            # For payment events, surface the amount directly in the Slack message
            amount_str = ""
            if trigger["name"] == "payment":
                match = _AMOUNT_RE.search(body_text)
                if match:
                    amount_str = f" — *{match.group(0).replace(' ','')}*"

            message = f"{trigger['emoji']} *{trigger['title']}*{amount_str}\n{summary}\n_{core.timestamp()}_"

            if "YOUR_" in webhook:
                log.warning(f"Slack not configured — would post: {message}")
                # Claim with a label so we don't re-summarise it every poll
                core.gmail_label(gmail, e["id"], GAOS_BROADCAST_LABEL)
                continue

            if core.post_to_slack(webhook, message):
                log.info(f"Posted to Slack: {trigger['title']}")
                posted += 1
                core.gmail_label(gmail, e["id"], GAOS_BROADCAST_LABEL)
                if trigger.get("mark_read"):
                    core.gmail_mark_read(gmail, e["id"])
            else:
                # Leave unlabelled and unread so the next poll retries the post
                log.warning(f"Slack post failed for {trigger['title']} — will retry.")

    return posted


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("module_07_team_broadcaster: Watching for business events to broadcast.")
    core.run_loop(lambda: process_events(gmail, cfg),
                  cfg["settings"]["check_every_seconds"])


if __name__ == "__main__":
    run()
