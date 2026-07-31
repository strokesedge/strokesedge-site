"""
StrokesEdge Twitter Auto-Poster — Queue manager

Takes generated tweets, checks for near-duplicates against what's already
queued, then routes each one to approved_queue.jsonl (link-free,
auto-post-eligible) or pending_review.jsonl (needs Brian's sign-off —
either because it's picks-phase, contains the site link, or tripped a
REVIEW_TRIGGER_WORDS keyword), sending an email alert for anything in
review, reusing the existing Gmail app password setup.
"""

import difflib
import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from config import (
    QUEUE_DIR, APPROVED_QUEUE, PENDING_REVIEW, REJECTED_LOG, MANUAL_POST_QUEUE,
    SKIPPED_DUPLICATES_LOG,
)
from generator import generate_tweets, needs_review
from approve import pending_reason_tag

GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
GMAIL_ADDRESS = "strokesedge@gmail.com"

# Near-duplicate similarity threshold (difflib.SequenceMatcher ratio, 0-1).
# 0.75 catches "same sentence, different player name swapped in" and exact
# rephrasings without also flagging two tweets that just happen to both
# mention "SG: Approach" or the tournament name — chosen as a reasonable
# middle ground, not empirically tuned against real duplicate pairs yet.
DUPLICATE_SIMILARITY_THRESHOLD = 0.75
DUPLICATE_CHECK_WINDOW = 20


def ensure_queue_dir():
    os.makedirs(QUEUE_DIR, exist_ok=True)
    for path in (APPROVED_QUEUE, PENDING_REVIEW, REJECTED_LOG, MANUAL_POST_QUEUE):
        if not os.path.exists(path):
            open(path, "a").close()


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path, record):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def recent_queued_texts(window=DUPLICATE_CHECK_WINDOW):
    """Last `window` tweet texts across every not-yet-posted queue —
    approved (about to auto-post), pending review, and manual post queue —
    newest-last across each file, most-recent `window` overall kept."""
    combined = load_jsonl(APPROVED_QUEUE) + load_jsonl(PENDING_REVIEW) + load_jsonl(MANUAL_POST_QUEUE)
    return [item["text"] for item in combined[-window:]]


def find_near_duplicate(new_text, existing_texts):
    """Returns the matched existing text if new_text is a near-duplicate of
    anything in existing_texts, else None. Simple ratio-based check
    (stdlib difflib, no extra dependency) rather than anything semantic —
    catches the common case (same content, one detail swapped) without
    needing an embeddings call for every draft tweet."""
    for existing in existing_texts:
        ratio = difflib.SequenceMatcher(None, new_text.lower(), existing.lower()).ratio()
        if ratio >= DUPLICATE_SIMILARITY_THRESHOLD:
            return existing
    return None


def log_skipped_duplicate(new_text, matched_text):
    with open(SKIPPED_DUPLICATES_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} SKIPPED (near-duplicate)\n")
        f.write(f"  NEW:     {new_text}\n")
        f.write(f"  MATCHED: {matched_text}\n\n")


def send_review_email(new_pending_items, total_pending_count):
    if not GMAIL_APP_PASSWORD:
        print("[queue_manager] GMAIL_APP_PASSWORD not set — skipping email alert. "
              "Check pending_review.jsonl manually.")
        return

    body_lines = [
        f"TOTAL PENDING REVIEW RIGHT NOW: {total_pending_count}",
        "",
        f"{len(new_pending_items)} new tweet(s) from this run need your approval:",
        "",
    ]
    for i, item in enumerate(new_pending_items, 1):
        body_lines.append(f"{i}. {pending_reason_tag(item['text'])}\n{item['text']}\n")
    body_lines.append(
        "\nReply to this email with e.g. \"approve 1\" or \"reject 2\" (indices refer to "
        "the FULL current pending list, not just what's shown above if a batch built up), "
        "or run: python approve.py"
    )
    body = "\n".join(body_lines)

    msg = MIMEText(body)
    msg["Subject"] = f"StrokesEdge: {total_pending_count} tweet(s) need approval"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"[queue_manager] Review email sent. Total pending: {total_pending_count}.")
    except Exception as e:
        print(f"[queue_manager] Failed to send review email: {e}")


def run():
    ensure_queue_dir()
    phase, tweets = generate_tweets()

    pending_batch = []
    approved_count = 0
    skipped_count = 0

    for t in tweets:
        existing_texts = recent_queued_texts()
        dup = find_near_duplicate(t, existing_texts)
        if dup:
            log_skipped_duplicate(t, dup)
            skipped_count += 1
            print(f"[skipped duplicate] {t[:80]}...")
            continue

        record = {
            "text": t,
            "phase": phase,
            "generated_at": datetime.now().isoformat(),
            "char_count": len(t),
        }
        if needs_review(t, phase):
            append_jsonl(PENDING_REVIEW, record)
            pending_batch.append(record)
        else:
            append_jsonl(APPROVED_QUEUE, record)
            approved_count += 1
            print(f"[auto-approved] {t}")

    if pending_batch:
        total_pending = len(load_jsonl(PENDING_REVIEW))
        send_review_email(pending_batch, total_pending)

    print(f"\nDone. Phase: {phase}. "
          f"{approved_count} auto-approved, {len(pending_batch)} pending review, "
          f"{skipped_count} skipped as duplicates.")


if __name__ == "__main__":
    run()
