"""
utils/sharing_utils.py
------------------------
Generates share links so a draft can be pushed to a teammate on
WhatsApp/Slack for a quick "does this sound right?" before publishing.
Note: Slack doesn't support a generic "share text via URL" the way
WhatsApp's click-to-chat does, so for Slack we use an Incoming Webhook
(recommended, one-click "post to channel") with a manual-copy fallback.
"""

import os
import urllib.parse
import requests


def generate_whatsapp_link(text: str, phone_number: str = None) -> str:
    """
    phone_number in international format without '+' or spaces, e.g. '919876543210'.
    If omitted, opens WhatsApp's contact picker instead of a specific chat.
    """
    encoded = urllib.parse.quote(text)
    if phone_number:
        return f"https://wa.me/{phone_number}?text={encoded}"
    return f"https://api.whatsapp.com/send?text={encoded}"


def post_to_slack(text: str, webhook_url: str = None) -> bool:
    """
    Posts directly into a Slack channel via an Incoming Webhook.
    Set up at: https://api.slack.com/messaging/webhooks
    Store the resulting URL as SLACK_WEBHOOK_URL in .env (per-workspace if
    each company has its own Slack).
    """
    webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return False
    resp = requests.post(webhook_url, json={"text": text}, timeout=10)
    return resp.status_code == 200


def generate_share_bundle(text: str, phone_number: str = None) -> dict:
    return {
        "whatsapp": generate_whatsapp_link(text, phone_number),
        "slack_webhook_configured": bool(os.getenv("SLACK_WEBHOOK_URL")),
        "raw_text": text,
    }
