"""
Stream 2 — scheduled entry point for the hourly picks-vs-live-standings
update. Task Scheduler should fire this every 15 minutes, always, same
ticker pattern as run_cycle.py; this script decides for itself whether
it's actually time to run, based on config.STANDINGS_CADENCE_MINUTES
(~60 min) and its own schedule state file (kept separate from
run_cycle.py's so the two cadences never collide or share state).

Only ever runs while shared.tracker.is_picks_phase() is True — i.e. there
are open bets logged for the current tournament — since there is nothing
to compare against a live leaderboard otherwise. Naturally stops once
every bet settles; final results stay Stream 1's recap job, never this
script's.

Same exit-code contract as run_cycle.py (see its docstring for the
2026-08-05 incident this guards against): this process exits 0 only when
it correctly did nothing, emailed an update, or hit a recognized/logged
content failure (no picks phase, no live data match — normal operation).
Any unrecognized failure exits 1 so Task Scheduler's Last Run Result
reflects it.

Never imports or calls anything from stream1_auto — this stream cannot
post to X and never touches post_tweets.py.

--force bypasses the active-hours/interval/picks-phase checks (manual/test
trigger).
"""

import argparse
import json
import os
import sys
from datetime import datetime

_SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from email_utils import send_email
from tracker import is_picks_phase

from config import (
    ACTIVE_START_HOUR, ACTIVE_END_HOUR, STANDINGS_CADENCE_MINUTES,
    STANDINGS_SCHEDULE_STATE, FAILED_LOG,
)
from standings_generator import generate_standings_options, CATEGORY
from emailer import send_manual_post_batch, append_jsonl


def load_state():
    if os.path.exists(STANDINGS_SCHEDULE_STATE):
        with open(STANDINGS_SCHEDULE_STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_generated_at": None}


def save_state(state):
    os.makedirs(os.path.dirname(STANDINGS_SCHEDULE_STATE), exist_ok=True)
    with open(STANDINGS_SCHEDULE_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def in_active_window(now):
    return ACTIVE_START_HOUR <= now.hour < ACTIVE_END_HOUR


def should_run(now, state):
    last = state.get("last_generated_at")
    if not last:
        return True
    elapsed_minutes = (now - datetime.fromisoformat(last)).total_seconds() / 60
    return elapsed_minutes >= STANDINGS_CADENCE_MINUTES


def _fail(now, reason):
    print(f"[stream2-standings] FAILURE: {reason}")
    append_jsonl(FAILED_LOG, {
        "category": CATEGORY, "error": reason, "failed_at": now.isoformat(),
    })
    send_email(
        "StrokesEdge Stream 2: standings update failed, nothing emailed",
        f"A Stream 2 picks-vs-standings scheduled run failed this slot — no update was "
        f"emailed to you.\n\nReason: {reason}\n\n"
        f"Logged to failed_log.jsonl. This process is also exiting non-zero so Task "
        f"Scheduler's Last Run Result reflects the failure directly.",
    )
    return 1


def run(force=False):
    now = datetime.now()

    if not force and not in_active_window(now):
        print(f"[stream2-standings] {now.isoformat(timespec='minutes')} — outside active hours "
              f"({ACTIVE_START_HOUR}:00-{ACTIVE_END_HOUR}:00), skipping.")
        return 0

    state = load_state()

    if not force and not should_run(now, state):
        last = state.get("last_generated_at")
        elapsed = (now - datetime.fromisoformat(last)).total_seconds() / 60 if last else None
        print(f"[stream2-standings] {now.isoformat(timespec='minutes')} — cadence is "
              f"{STANDINGS_CADENCE_MINUTES} min, only {elapsed:.0f} min since last update, skipping.")
        return 0

    if not force and not is_picks_phase():
        print(f"[stream2-standings] {now.isoformat(timespec='minutes')} — no open picks logged "
              f"for the current tournament, nothing to compare against a live leaderboard yet, skipping.")
        return 0

    try:
        options, error_reason = generate_standings_options()
    except Exception as e:
        return _fail(now, f"generation raised an exception: {e!r}")

    if error_reason:
        append_jsonl(FAILED_LOG, {
            "category": CATEGORY, "error": error_reason, "failed_at": now.isoformat(),
        })
        print(f"[stream2-standings] Slot failed, nothing emailed — reason={error_reason}")
        state["last_generated_at"] = now.isoformat()
        save_state(state)
        return 0

    try:
        sent = send_manual_post_batch(CATEGORY, options, image_path=None)
    except Exception as e:
        return _fail(now, f"send_manual_post_batch raised an exception: {e!r}")

    if not sent:
        return _fail(now, "send_manual_post_batch returned False — email did not go out")

    print(f"[stream2-standings] Batch emailed=True — {len(options)} option(s).")
    state["last_generated_at"] = now.isoformat()
    save_state(state)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                         help="Bypass active-hours, interval, and picks-phase checks — run right now regardless.")
    args = parser.parse_args()
    sys.exit(run(force=args.force))
