"""
Stream 2 — delivery. One email per slot, sent immediately when that slot's
options are ready (not batched into a daily digest), clearly labeled so
Brian can tell at a glance this is copy/paste-it-yourself content, never
something the bot already posted.
"""

import json
import os
import sys
from datetime import datetime

_SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

from email_utils import send_email
from tournament_config import TOURNAMENT

from config import SENT_LOG


def append_jsonl(path, record):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def send_manual_post_batch(category, options, image_path=None):
    """image_path (optional): a local chart PNG (course_facts/methodology/
    course_fit only — see chart_gen.should_chart) to attach alongside the
    text options. The caller (run_cycle.py) owns the file's lifecycle —
    this function only reads it, doesn't delete it."""
    subject = f"MANUAL POST — pick one, copy, paste ({TOURNAMENT['name']}, {category})"

    body_lines = [
        f"{len(options)} phrasing option(s) for this slot — category: {category}.",
        "Pick the one you like, copy it, paste it into X yourself. Nothing here",
        "auto-posts or costs anything via the API.",
        "",
    ]
    if image_path:
        body_lines.insert(0, "*** CHART ATTACHED — grab BOTH the text below AND the attached "
                              "image when you post. ***")
        body_lines.insert(1, "")
    for i, opt in enumerate(options, 1):
        body_lines.append(f"--- Option {i} ({len(opt)} chars) ---")
        body_lines.append(opt)
        body_lines.append("")

    body = "\n".join(body_lines)
    sent = send_email(subject, body, attachment_path=image_path)

    append_jsonl(SENT_LOG, {
        "category": category,
        "options": options,
        "had_chart": image_path is not None,
        "email_sent": sent,
        "sent_at": datetime.now().isoformat(),
    })
    return sent
