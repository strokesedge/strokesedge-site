"""
StrokesEdge Twitter Auto-Poster — Approve / reject pending tweets, and mark
manual posts done

Usage:
    python approve.py               # lists all pending tweets with index numbers
    python approve.py 2              # moves item #2 from pending_review to
                                      # approved_queue.jsonl (link-free) or
                                      # manual_post_queue.jsonl (contains link)
    python approve.py 2 --edit "new tweet text here"   # edit then approve
    python approve.py 2 --reject     # discards item #2 instead of approving it
    python approve.py --manual       # lists the manual-post queue with index numbers
    python approve.py --posted 3     # marks manual-post-queue item #3 as posted

approve()/reject()/mark_posted() are imported directly by check_approvals.py
(reply-based approval over Gmail) — they're the single source of truth for
what "approve"/"reject"/"posted" actually do to the queue files, so the CLI
and the email flow can never drift apart.
"""

import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from config import (
    PENDING_REVIEW, APPROVED_QUEUE, REJECTED_LOG, MANUAL_POST_QUEUE,
    POSTED_LOG, contains_site_link,
)

TWITTER_CHAR_LIMIT = 280


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


def pending_reason_tag(text):
    if contains_site_link(text):
        return "[MANUAL — COPY/PASTE, contains link]"
    if len(text) > TWITTER_CHAR_LIMIT:
        return f"[OVER LENGTH — {len(text)} chars, edit before approving]"
    return "[WILL AUTO-POST IF APPROVED]"


def list_pending():
    pending = load_jsonl(PENDING_REVIEW)
    if not pending:
        print("No tweets pending review.")
        return
    for i, item in enumerate(pending, 1):
        print(f"\n[{i}] {pending_reason_tag(item['text'])} ({item['char_count']} chars, phase={item['phase']})")
        print(item["text"])


def list_manual_queue():
    manual = load_jsonl(MANUAL_POST_QUEUE)
    if not manual:
        print("Manual post queue is empty.")
        return
    for i, item in enumerate(manual, 1):
        print(f"\n[{i}] ({item['char_count']} chars, phase={item['phase']})")
        print(item["text"])


def approve(index, edited_text=None):
    """Returns the approved item dict on success, or None if index was
    invalid (caller — CLI or check_approvals.py — decides how to report
    that; this function never guesses or clamps an out-of-range index).

    Destination depends on link content, not phase: approved_queue.jsonl is
    link-free by contract (post_tweets.py auto-posts everything in it), so
    anything containing the site link goes to manual_post_queue.jsonl
    instead — Brian posts those himself. This is checked here (not just at
    generation time) because an edited approval (--edit) could introduce a
    link that wasn't there originally, or a pending item could have been
    flagged for review by REVIEW_TRIGGER_WORDS alone with no link at all,
    in which case approving it correctly still auto-posts."""
    pending = load_jsonl(PENDING_REVIEW)
    if index < 1 or index > len(pending):
        print(f"Invalid index. There are {len(pending)} pending item(s).")
        return None

    item = pending.pop(index - 1)
    if edited_text:
        item["text"] = edited_text
        item["char_count"] = len(edited_text)
        item["edited"] = True

    if contains_site_link(item["text"]):
        # Bound for manual copy/paste — Brian sees and would naturally trim
        # an over-length tweet himself in X's own compose box, so no length
        # gate needed on this path.
        append_jsonl(MANUAL_POST_QUEUE, item)
        write_jsonl(PENDING_REVIEW, pending)
        print(f"Approved — routed to manual post queue (contains link, post it yourself):\n{item['text']}")
        return item

    if len(item["text"]) > TWITTER_CHAR_LIMIT:
        # Bound for auto-posting — nobody looks at this again before
        # post_tweets.py calls the X API, which would reject an over-length
        # post every single run, forever, on the exact same tweet. Refuse
        # the approval outright rather than let that failure loop start;
        # put the item back where it came from so it isn't lost.
        pending.insert(index - 1, item)
        write_jsonl(PENDING_REVIEW, pending)
        print(f"NOT approved — {len(item['text'])} chars exceeds the {TWITTER_CHAR_LIMIT}-char "
              f"limit and this would auto-post unattended. Edit it first: "
              f"python approve.py {index} --edit \"shorter text\"")
        return None

    append_jsonl(APPROVED_QUEUE, item)
    write_jsonl(PENDING_REVIEW, pending)
    print(f"Approved — will auto-post:\n{item['text']}")
    return item


def reject(index):
    """Discards pending item #index — removes it from pending_review.jsonl
    without moving it to approved_queue.jsonl. Logged to rejected_log.jsonl
    rather than silently deleted, so there's still an audit trail (same
    reasoning as posted_log.jsonl on the posting side). Returns the
    rejected item dict on success, or None if index was invalid."""
    pending = load_jsonl(PENDING_REVIEW)
    if index < 1 or index > len(pending):
        print(f"Invalid index. There are {len(pending)} pending item(s).")
        return None

    item = pending.pop(index - 1)
    item["status"] = "rejected"
    append_jsonl(REJECTED_LOG, item)
    write_jsonl(PENDING_REVIEW, pending)
    print(f"Rejected:\n{item['text']}")
    return item


def mark_posted(index):
    """Marks manual_post_queue.jsonl item #index as posted — for a tweet
    Brian posted by hand (copy/paste, since it contains the site link and
    never touches post_tweets.py / the X API). Logged to posted_log.jsonl
    with posted_via='manual' so duplicate-detection sees it like any other
    posted tweet, but the monthly auto-post budget check (which only cares
    about real API spend) ignores it — see config.MONTHLY_AUTO_POST_BUDGET.
    Returns the item dict on success, or None if index was invalid."""
    manual = load_jsonl(MANUAL_POST_QUEUE)
    if index < 1 or index > len(manual):
        print(f"Invalid index. There are {len(manual)} item(s) in the manual post queue.")
        return None

    item = manual.pop(index - 1)
    item["status"] = "posted"
    item["posted_via"] = "manual"
    append_jsonl(POSTED_LOG, item)
    write_jsonl(MANUAL_POST_QUEUE, manual)
    print(f"Marked posted:\n{item['text']}")
    return item


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("index", nargs="?", type=int, help="Index of tweet to approve/reject")
    parser.add_argument("--edit", type=str, default=None, help="Replace tweet text before approving")
    parser.add_argument("--reject", action="store_true", help="Reject instead of approve")
    parser.add_argument("--manual", action="store_true", help="List the manual post queue instead of pending review")
    parser.add_argument("--posted", type=int, default=None, metavar="INDEX",
                         help="Mark manual post queue item INDEX as posted by hand")
    args = parser.parse_args()

    if args.posted is not None:
        mark_posted(args.posted)
    elif args.manual:
        list_manual_queue()
    elif args.index is None:
        list_pending()
    elif args.reject:
        if args.edit:
            print("--edit has no effect with --reject, ignoring.")
        reject(args.index)
    else:
        approve(args.index, args.edit)
