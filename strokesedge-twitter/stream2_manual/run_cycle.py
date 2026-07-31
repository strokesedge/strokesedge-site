"""
Stream 2 — scheduled entry point. Task Scheduler should fire this every 15
minutes, always; this script decides for itself whether it's actually time
to generate a batch, based on config.CADENCE_MINUTES (~90 min, targeting
~10 batches/day across the 7am-11pm active window).

Generate and email happen together, immediately, per slot — no daily
digest, no approval step, no queue for Brian to check. He either gets the
email or he doesn't; a failed slot is logged (FAILED_LOG) and skipped
rather than retried in a loop, since the next scheduled tick will attempt
a fresh slot anyway.

Never imports or calls anything from stream1_auto — this stream cannot
post to X and never touches post_tweets.py.

--force bypasses the active-hours/interval checks (manual/test trigger).
"""

import argparse
import json
import os
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from config import ACTIVE_START_HOUR, ACTIVE_END_HOUR, CADENCE_MINUTES, GENERATE_SCHEDULE_STATE, FAILED_LOG
from generator import generate_slot_options
from emailer import send_manual_post_batch, append_jsonl


def load_state():
    if os.path.exists(GENERATE_SCHEDULE_STATE):
        with open(GENERATE_SCHEDULE_STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_generated_at": None, "last_category": None}


def save_state(state):
    os.makedirs(os.path.dirname(GENERATE_SCHEDULE_STATE), exist_ok=True)
    with open(GENERATE_SCHEDULE_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def in_active_window(now):
    return ACTIVE_START_HOUR <= now.hour < ACTIVE_END_HOUR


def should_run(now, state):
    last = state.get("last_generated_at")
    if not last:
        return True
    elapsed_minutes = (now - datetime.fromisoformat(last)).total_seconds() / 60
    return elapsed_minutes >= CADENCE_MINUTES


def run(force=False):
    now = datetime.now()

    if not force and not in_active_window(now):
        print(f"[stream2] {now.isoformat(timespec='minutes')} — outside active hours "
              f"({ACTIVE_START_HOUR}:00-{ACTIVE_END_HOUR}:00), skipping.")
        return

    state = load_state()

    if not force and not should_run(now, state):
        last = state.get("last_generated_at")
        elapsed = (now - datetime.fromisoformat(last)).total_seconds() / 60 if last else None
        print(f"[stream2] {now.isoformat(timespec='minutes')} — cadence is {CADENCE_MINUTES} min, "
              f"only {elapsed:.0f} min since last batch, skipping.")
        return

    # A transient failure here (network blip, API hiccup) must not crash
    # with a raw traceback and must not update last_generated_at — leaving
    # the timestamp stale means the very next scheduled tick (15 min
    # later) will simply try again, rather than waiting out a full
    # cadence interval for a slot that never actually ran.
    try:
        category, options, error_reason = generate_slot_options(last_category=state.get("last_category"), now=now)
    except Exception as e:
        print(f"[stream2] Generation failed, will retry next tick: {e}")
        return

    if error_reason:
        append_jsonl(FAILED_LOG, {
            "category": category, "error": error_reason, "failed_at": now.isoformat(),
        })
        print(f"[stream2] Slot failed, nothing emailed — category={category}, reason={error_reason}")
    else:
        sent = send_manual_post_batch(category, options)
        print(f"[stream2] Batch emailed={sent} — category={category}, {len(options)} option(s).")

    state["last_generated_at"] = now.isoformat()
    state["last_category"] = category
    save_state(state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                         help="Bypass active-hours and interval checks — run right now regardless.")
    args = parser.parse_args()
    run(force=args.force)
