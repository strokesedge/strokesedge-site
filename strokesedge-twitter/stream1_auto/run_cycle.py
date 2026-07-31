"""
Stream 1 — scheduled entry point. Task Scheduler should fire this every 15
minutes, always; this script decides for itself whether it's actually time
to generate+post, based on config.CADENCE_MINUTES (~64 min, computed from
the ~15/day target across the 7am-11pm active window). A 15-minute tick
divides evenly into that so the cadence never drifts.

Generate and post happen together in one call, with nothing in between —
this stream has no human-review step by design. The automated safety net
in generator.py and the hard link re-check in post_tweets.py are what
stand in for a human here.

--force bypasses the active-hours/interval checks (manual/test trigger).
"""

import argparse
import json
import os
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from config import ACTIVE_START_HOUR, ACTIVE_END_HOUR, CADENCE_MINUTES, GENERATE_SCHEDULE_STATE, FLAGGED_LOG
from generator import generate_slot
from post_tweets import post_if_safe, append_jsonl


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


def run(force=False, dry_run=False):
    now = datetime.now()

    if not force and not in_active_window(now):
        print(f"[stream1] {now.isoformat(timespec='minutes')} — outside active hours "
              f"({ACTIVE_START_HOUR}:00-{ACTIVE_END_HOUR}:00), skipping.")
        return

    state = load_state()

    if not force and not should_run(now, state):
        last = state.get("last_generated_at")
        elapsed = (now - datetime.fromisoformat(last)).total_seconds() / 60 if last else None
        print(f"[stream1] {now.isoformat(timespec='minutes')} — cadence is {CADENCE_MINUTES} min, "
              f"only {elapsed:.0f} min since last slot, skipping.")
        return

    # A transient failure here (network blip, API hiccup) must not crash
    # with a raw traceback and must not update last_generated_at — leaving
    # the timestamp stale means the very next scheduled tick (15 min
    # later) will simply try again, rather than waiting out a full
    # cadence interval for a slot that never actually ran.
    try:
        category, text, flag_reason = generate_slot(last_category=state.get("last_category"), now=now)
    except Exception as e:
        print(f"[stream1] Generation failed, will retry next tick: {e}")
        return

    if flag_reason:
        append_jsonl(FLAGGED_LOG, {
            "category": category, "text": text, "reason": flag_reason,
            "flagged_at": now.isoformat(),
        })
        print(f"[stream1] Slot flagged, NOT posted — category={category}, reason={flag_reason}")
    else:
        try:
            post_if_safe(category, text, dry_run=dry_run)
        except Exception as e:
            print(f"[stream1] Posting failed, will retry next tick: {e}")
            return

    state["last_generated_at"] = now.isoformat()
    state["last_category"] = category
    save_state(state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                         help="Bypass active-hours and interval checks — run right now regardless.")
    parser.add_argument("--dry-run", action="store_true",
                         help="Generate and run safety checks, but don't actually call the X API.")
    args = parser.parse_args()
    run(force=args.force, dry_run=args.dry_run)
