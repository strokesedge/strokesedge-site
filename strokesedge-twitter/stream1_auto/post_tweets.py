"""
Stream 1 — the actual X API call. This is the last line of code that runs
before a tweet becomes real and public, so it re-checks the link ban
itself rather than trusting generator.py got it right — belt and
suspenders, per an explicit requirement that this hard check live here,
not just in the prompt or in generator.py's safety net.

Requires these environment variables (same pattern as ANTHROPIC_API_KEY):
    X_API_KEY
    X_API_SECRET
    X_ACCESS_TOKEN
    X_ACCESS_TOKEN_SECRET
"""

import json
import os
import sys
from datetime import datetime

_SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

import tweepy

from link_check import contains_site_link
from email_utils import send_email

from config import POSTED_LOG, FLAGGED_LOG, MONTHLY_AUTO_POST_BUDGET, COST_PER_AUTO_POST


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path, record):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def get_client():
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def current_month_post_count():
    now = datetime.now()
    count = 0
    for item in load_jsonl(POSTED_LOG):
        ts = item.get("posted_at")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if dt.year == now.year and dt.month == now.month:
            count += 1
    return count


def post_if_safe(category, text, dry_run=False):
    """The only entry point run_cycle.py should call. Returns True if
    posted (or would post, under --dry-run), False otherwise — every
    False path logs why to FLAGGED_LOG rather than silently dropping."""

    # HARD SAFETY NET — re-checked here even though generator.py already
    # checked, because this is the last point before a real, irreversible
    # public API call. If a link ever slips through upstream, refuse and
    # log rather than post.
    if contains_site_link(text):
        append_jsonl(FLAGGED_LOG, {
            "category": category, "text": text,
            "reason": "post_tweets.py hard link check caught a link that "
                      "should never have reached this point — investigate generator.py",
            "flagged_at": datetime.now().isoformat(),
        })
        print(f"[post_tweets] REFUSED — contains site link, this should never happen upstream: {text[:80]}")
        send_email(
            "StrokesEdge Stream 1: link safety net caught a tweet — investigate",
            f"A Stream 1 tweet reached post_tweets.py containing a site link, which should "
            f"be impossible (generator.py already filters this). It was NOT posted.\n\n"
            f"Category: {category}\nText: {text}",
        )
        return False

    month_count = current_month_post_count()
    if month_count >= MONTHLY_AUTO_POST_BUDGET:
        print(f"[post_tweets] Monthly auto-post budget ({MONTHLY_AUTO_POST_BUDGET}) reached "
              f"({month_count} posted this month) — holding this slot.")
        send_email(
            "StrokesEdge Stream 1: monthly auto-post budget reached",
            f"This month's Stream 1 post count ({month_count}) has reached the self-imposed "
            f"budget of {MONTHLY_AUTO_POST_BUDGET} (config.MONTHLY_AUTO_POST_BUDGET). This is a "
            f"safety ceiling, not a real X-enforced cap — raise it in config.py if expected. "
            f"This run's tweet was skipped, not posted:\n\n{text}",
        )
        return False

    if dry_run:
        print(f"[DRY RUN] Would post ({category}, {len(text)} chars, "
              f"${COST_PER_AUTO_POST:.3f}):\n{text}")
        return True

    client = get_client()
    try:
        resp = client.create_tweet(text=text)
        append_jsonl(POSTED_LOG, {
            "category": category,
            "text": text,
            "char_count": len(text),
            "posted_id": resp.data.get("id"),
            "posted_at": datetime.now().isoformat(),
        })
        print(f"[post_tweets] Posted ({category}): {text[:80]}...")
        return True
    except Exception as e:
        append_jsonl(FLAGGED_LOG, {
            "category": category, "text": text,
            "reason": f"X API call failed: {e}",
            "flagged_at": datetime.now().isoformat(),
        })
        print(f"[post_tweets] FAILED to post: {e}")
        return False
