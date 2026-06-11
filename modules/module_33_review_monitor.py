"""
GAOS™ MODULE 33 — Review Monitor
Virtual Marketer | £199/mo bundle | Standalone: £800

Watches Gmail for incoming review notifications from Google
(Google sends automatic emails when a new review is posted on
your Google Business Profile). When a review arrives:

  Positive review (4-5 stars):
    → AI drafts a warm thank-you reply for the owner to approve
    → Logs the review and sentiment to a Reviews sheet
    → Optionally quotes the review in the next Newsletter

  Negative review (1-3 stars):
    → Alerts the owner immediately via SMS and email
    → AI drafts a calm, professional response for the owner to review
    → Logs for tracking

No third-party API needed. Works from the notification emails
Google already sends to the business Gmail inbox.

Sheet tab required: Reviews_Log
Columns: Date | Platform | Reviewer | Stars | Review | Draft Reply | Actioned

Target: Any business with a Google Business Profile.
Pain:   Negative reviews going unanswered for days. Positive reviews
        with no response (looks like the business doesn't care).
"""

import re
from datetime import datetime
import gaos_core as core

log = core.get_logger("review_monitor")

# Google sends review notifications from this domain
REVIEW_QUERY = 'is:unread from:@google.com (subject:"New review" OR subject:"review" OR subject:"rated your business")'


def extract_stars(text):
    """Attempts to extract star rating from review notification email."""
    patterns = [
        r'(\d)\s*(?:star|★|out of 5)',
        r'rated.*?(\d)(?:\s*/\s*5|\s*stars?)',
        r'(\d)\s*(?:out of|\/)\s*5',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
    return None


def build_positive_response(reviewer, stars, review_text, business_name):
    return (
        f"Write a warm, genuine Google review response from {business_name} "
        f"to {reviewer or 'a customer'} who gave {stars} stars. "
        f"Review text: {review_text[:200] if review_text else 'positive feedback'}\n\n"
        f"Keep it under 60 words. Personal, grateful, not generic. "
        f"Return ONLY the response text."
    )


def build_negative_response(reviewer, stars, review_text, business_name):
    return (
        f"Write a professional, calm Google review response from {business_name} "
        f"to {reviewer or 'a customer'} who gave {stars} stars. "
        f"Review text: {review_text[:200] if review_text else 'negative feedback'}\n\n"
        f"Acknowledge their concern, apologise for their experience, invite them "
        f"to contact us directly to resolve. Under 80 words. "
        f"Return ONLY the response text."
    )


def process_review_email(gmail, cfg, msg_id):
    """Processes a single Google review notification email."""
    try:
        detail  = gmail.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()
        payload = detail.get("payload", {})
        headers = {h["name"]: h["value"]
                   for h in payload.get("headers", [])}
        snippet = detail.get("snippet", "")
        subject = headers.get("Subject", "")

        stars    = extract_stars(snippet) or extract_stars(subject)
        reviewer = None
        m = re.search(r'"([^"]+)"\s+(?:rated|reviewed|left)', snippet + " " + subject)
        if m:
            reviewer = m.group(1)

        # Unknown ratings get the needs-attention path — a 1-star review
        # whose format we couldn't parse must never be silently filed
        # as positive.
        is_negative = stars is None or stars <= 3
        stars_label = f"{stars}★" if stars is not None else "rating unknown"
        business    = cfg["business"]["name"]
        sheet_id    = cfg["google_sheets"]["sheet_id"]
        tab         = cfg["google_sheets"]["tabs"].get("reviews_log", "Reviews_Log")

        sentiment = "needs attention" if is_negative else "positive"
        log.info(f"Review detected: {stars_label} from {reviewer or 'unknown'} ({sentiment})")

        # Mark read FIRST: if any alert below fails transiently, retrying
        # the whole email would re-SMS/re-log on every poll forever.
        gmail.users().messages().modify(
            userId="me", id=msg_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()

        # Draft response
        if is_negative:
            prompt = build_negative_response(reviewer, stars, snippet, business)
        else:
            prompt = build_positive_response(reviewer, stars, snippet, business)

        response_draft = core.ask_deepseek(
            cfg["deepseek"]["api_key"], prompt,
            max_tokens=150, expect_json=False
        ) or "(Could not generate response — please write manually)"

        # Canonical Reviews_Log:
        # [Date, Platform, Reviewer, Stars, Review, Draft Reply, Actioned]
        core.sheets_append_row(sheet_id, tab, [
            core.timestamp(),
            "Google",
            reviewer or "Unknown",
            stars if stars is not None else "",
            snippet[:150],
            response_draft[:200],
            "Draft ready"
        ])

        # Alert for negative reviews
        if is_negative:
            tw = cfg["twilio"]
            if "YOUR_" not in tw["account_sid"]:
                core.send_sms(tw["account_sid"], tw["auth_token"],
                              tw["from_number"], tw["owner_mobile"],
                              f"⚠ New review needs attention ({stars_label}) from "
                              f"{reviewer or 'a customer'}. "
                              f"Check your Reviews_Log for a draft response.")

            core.gmail_send(
                gmail, cfg["gmail"]["alert_email"], cfg["gmail"]["watch_inbox"],
                f"⚠ Review needs attention ({stars_label}) — draft response ready",
                f"Review from: {reviewer or 'Unknown'}\nRating: {stars_label}\n\n"
                f"What they said:\n{snippet[:300]}\n\n"
                f"Suggested response:\n{response_draft}\n\n"
                f"Post your response at: https://business.google.com\n\n"
                f"Aether Frameworks — GAOS™ Review Monitor"
            )

            # Also alert via Slack so the team sees it immediately
            slack_url = cfg.get("slack", {}).get("webhook_url", "")
            if slack_url and "YOUR_" not in slack_url:
                core.post_to_slack(slack_url,
                    f"⚠ *Review needs attention ({stars_label})* from {reviewer or 'a customer'}\n"
                    f"{snippet[:150]}\n_Draft response ready — check your email._"
                )
        else:
            # Save positive response as a draft
            core.gmail_send(
                gmail, cfg["gmail"]["alert_email"], cfg["gmail"]["watch_inbox"],
                f"✓ New {stars_label} review — response draft ready",
                f"Review from: {reviewer or 'a happy customer'}\n\n"
                f"Suggested response to post:\n{response_draft}\n\n"
                f"Post at: https://business.google.com\n\n"
                f"Aether Frameworks — GAOS™ Review Monitor"
            )

        return True

    except Exception as e:
        log.error(f"Error processing review email {msg_id}: {e}")
        return False


def scan(gmail, cfg):
    """Engine-compatible scan function."""
    emails = core.gmail_search(gmail, REVIEW_QUERY)
    for e in emails:
        process_review_email(gmail, cfg, e["id"])


def run():
    cfg   = core.load_config()
    gmail = core.connect_gmail()
    log.info("module_33_review_monitor: Watching for Google review notifications.")
    core.run_loop(lambda: scan(gmail, cfg),
                  cfg.get("settings", {}).get("check_every_seconds", 300))


if __name__ == "__main__":
    run()
