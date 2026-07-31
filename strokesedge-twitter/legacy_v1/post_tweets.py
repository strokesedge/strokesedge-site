"""
StrokesEdge Twitter Auto-Poster — Post approved tweets

Reads approved_queue.jsonl, posts each tweet via the X API (OAuth 1.0a,
Read+Write app), then moves it to posted_log.jsonl so it's never posted
twice. Two hard gates before anything actually calls the API:

1. LINK SAFETY NET (2026-07-30) — approved_queue.jsonl is supposed to be
   link-free by construction (generator.py forbids the link in auto-post
   content, and needs_review()/approve() both route anything with a link
   to manual_post_queue.jsonl instead). This re-checks anyway right before
   posting, because this is the last point before a real API call and an
   irreversible public post — if a link ever slips through upstream, it's
   rerouted to manual_post_queue.jsonl here rather than posted.
2. MONTHLY AUTO-POST BUDGET — a self-imposed ceiling (config.
   MONTHLY_AUTO_POST_BUDGET), not a real X-enforced cap (X's pay-per-use
   pricing has no monthly cap, just a per-post charge) — this exists so a
   scheduling bug can't quietly run up a real bill unattended. If posting
   an item would push this month's API-post count over the budget, it's
   held in approved_queue.jsonl (not discarded) and ONE summary email goes
   out, rather than failing silently or spamming an email per held tweet.

Requires these environment variables to be set (Windows env vars, same
pattern as ANTHROPIC_API_KEY / GMAIL_APP_PASSWORD):
    X_API_KEY
    X_API_SECRET
    X_ACCESS_TOKEN
    X_ACCESS_TOKEN_SECRET
"""

import json
import os
import smtplib
import sys
import time
from datetime import datetime
from email.mime.text import MIMEText

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

import tweepy

from config import APPROVED_QUEUE, POSTED_LOG, MANUAL_POST_QUEUE, MONTHLY_AUTO_POST_BUDGET, contains_site_link

GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
GMAIL_ADDRESS = "strokesedge@gmail.com"


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def append_jsonl(path, record):
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


def current_month_api_post_count():
    """Counts posted_log.jsonl entries that were real API posts (posted_via
    == 'api') this calendar month — manual posts (posted_via == 'manual',
    from approve.py's mark_posted()) never cost anything via the API and
    don't count against the budget. Missing posted_via (older log entries
    from before this field existed) is treated as 'api' — every real post
    before this change went through post_tweets.py, so that's the correct
    default rather than undercounting historical spend."""
    now = datetime.now()
    count = 0
    for item in load_jsonl(POSTED_LOG):
        if item.get("posted_via", "api") != "api":
            continue
        ts = item.get("generated_at") or item.get("posted_at")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if dt.year == now.year and dt.month == now.month:
            count += 1
    return count


def send_budget_email(held_count, current_count):
    if not GMAIL_APP_PASSWORD:
        print(f"[post_tweets] GMAIL_APP_PASSWORD not set — skipping budget alert email. "
              f"{held_count} tweet(s) held back this run, {current_count} API posts so far this month.")
        return
    body = (
        f"{held_count} tweet(s) were NOT posted this run because posting them would have "
        f"pushed this month's API post count over the {MONTHLY_AUTO_POST_BUDGET}-post budget "
        f"(config.MONTHLY_AUTO_POST_BUDGET).\n\n"
        f"Current month's API post count: {current_count}\n\n"
        f"This is a self-imposed safety ceiling, not a real X-enforced cap (pay-per-use pricing "
        f"has no monthly cap, just a per-post charge) — raise MONTHLY_AUTO_POST_BUDGET in config.py "
        f"if this was expected. Held tweets remain in approved_queue.jsonl and will post on a "
        f"future run once the budget resets or is raised."
    )
    msg = MIMEText(body)
    msg["Subject"] = f"StrokesEdge: {held_count} tweet(s) held — monthly auto-post budget reached"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"[post_tweets] Budget alert email sent ({held_count} held).")
    except Exception as e:
        print(f"[post_tweets] Failed to send budget alert email: {e}")


def post_all_approved(dry_run=False):
    approved = load_jsonl(APPROVED_QUEUE)
    if not approved:
        print("No approved tweets waiting to post.")
        return

    if dry_run:
        print(f"[DRY RUN] Would post {len(approved)} tweet(s):")
        for item in approved:
            print(f"\n---\n{item['text']}")
        return

    client = get_client()
    remaining = []
    held_for_budget = 0
    rerouted_for_link = 0
    api_post_count_this_month = current_month_api_post_count()

    for item in approved:
        # Hard safety net — see module docstring. Checked before the budget
        # count so a link-containing item never consumes budget headroom
        # it was never entitled to in the first place.
        if contains_site_link(item["text"]):
            append_jsonl(MANUAL_POST_QUEUE, item)
            rerouted_for_link += 1
            print(f"REROUTED (contains link, never auto-post): {item['text'][:60]}...")
            continue

        if api_post_count_this_month >= MONTHLY_AUTO_POST_BUDGET:
            remaining.append(item)  # held, not discarded — stays in approved_queue.jsonl
            held_for_budget += 1
            continue

        try:
            resp = client.create_tweet(text=item["text"])
            item["posted_id"] = resp.data.get("id")
            item["status"] = "posted"
            item["posted_via"] = "api"
            item["posted_at"] = datetime.now().isoformat()
            append_jsonl(POSTED_LOG, item)
            api_post_count_this_month += 1
            print(f"Posted: {item['text'][:60]}...")
            time.sleep(2)  # small buffer between posts
        except Exception as e:
            item["status"] = "failed"
            item["error"] = str(e)
            remaining.append(item)  # keep failed ones in the queue to retry
            print(f"FAILED to post: {item['text'][:60]}... — {e}")

    write_jsonl(APPROVED_QUEUE, remaining)

    if held_for_budget:
        send_budget_email(held_for_budget, api_post_count_this_month)

    posted_count = len(approved) - len(remaining) - rerouted_for_link
    print(f"\nDone. {posted_count} posted, {len(remaining)} failed/held, "
          f"{rerouted_for_link} rerouted to manual queue (contained a link).")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    post_all_approved(dry_run=dry_run)
