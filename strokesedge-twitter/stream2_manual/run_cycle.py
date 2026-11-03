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

Exit code contract (added after a 2026-08-05 incident: a raised exception
during generation was caught, printed, and swallowed — Task Scheduler
reported Last Run Result 0x0 "success" while nothing was generated,
emailed, or logged anywhere). This process exits 0 only when either
(a) it correctly did nothing because it wasn't yet time to run, (b) it
emailed a batch, or (c) it hit a recognized/logged content failure (bad
JSON, too few valid options, no source content — see FAILED_LOG, this is
normal operation, not a malfunction). Any other failure — an exception, or
send_manual_post_batch() returning False — now writes to FAILED_LOG, sends
a best-effort failure email, and exits 1 so Task Scheduler's Last Run
Result actually reflects it. A silent 0x0-while-nothing-happened outcome
must be structurally impossible after this.

--force bypasses the active-hours/interval checks (manual/test trigger).
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
from chart_gen import generate_chart_for_slot, cleanup_chart

from config import (
    ACTIVE_START_HOUR, ACTIVE_END_HOUR, CADENCE_MINUTES, GENERATE_SCHEDULE_STATE,
    FAILED_LOG, CHART_OUT_DIR,
)
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


def _fail(now, category, reason):
    """The one place a failed run reports itself. Writes a real FAILED_LOG
    entry (never just print()), best-effort emails a heads-up — send_email
    already fails safe and never raises, so this can't itself become a
    second silent failure — and returns the exit code the caller must
    propagate to sys.exit(). last_generated_at is deliberately NOT updated
    on this path (same reasoning as stream1_auto): leaving it stale means
    the very next 15-min tick retries sooner rather than waiting out a
    full cadence interval for a slot that never actually ran."""
    print(f"[stream2] FAILURE: {reason}")
    append_jsonl(FAILED_LOG, {
        "category": category, "error": reason, "failed_at": now.isoformat(),
    })
    send_email(
        "StrokesEdge Stream 2: scheduled run failed, nothing emailed",
        f"A Stream 2 scheduled run failed this slot — no batch was emailed to you.\n\n"
        f"Category: {category}\nReason: {reason}\n\n"
        f"Logged to failed_log.jsonl. This process is also exiting non-zero so Task "
        f"Scheduler's Last Run Result reflects the failure directly — treat that as "
        f"the authoritative signal, since if GMAIL_APP_PASSWORD itself is what's "
        f"broken, this email may not arrive either.",
    )
    return 1


def run(force=False):
    now = datetime.now()

    if not force and not in_active_window(now):
        print(f"[stream2] {now.isoformat(timespec='minutes')} — outside active hours "
              f"({ACTIVE_START_HOUR}:00-{ACTIVE_END_HOUR}:00), skipping.")
        return 0

    state = load_state()

    if not force and not should_run(now, state):
        last = state.get("last_generated_at")
        elapsed = (now - datetime.fromisoformat(last)).total_seconds() / 60 if last else None
        print(f"[stream2] {now.isoformat(timespec='minutes')} — cadence is {CADENCE_MINUTES} min, "
              f"only {elapsed:.0f} min since last batch, skipping.")
        return 0

    last_category = state.get("last_category")
    try:
        category, options, error_reason = generate_slot_options(last_category=last_category, now=now)
    except Exception as e:
        return _fail(now, last_category, f"generation raised an exception: {e!r}")

    if error_reason:
        append_jsonl(FAILED_LOG, {
            "category": category, "error": error_reason, "failed_at": now.isoformat(),
        })
        print(f"[stream2] Slot failed, nothing emailed — category={category}, reason={error_reason}")
        state["last_generated_at"] = now.isoformat()
        state["last_category"] = category
        save_state(state)
        return 0

    # Chart judgment runs against options[0] as representative — every
    # option in a slot is "the SAME underlying tweet" in different
    # phrasing (see generator.py), so checking one is enough. Best-effort
    # and category/content-gated (course_facts/methodology/course_fit
    # only) — (None, None) is the normal, expected outcome most slots.
    chart_path, chart_alt_text = generate_chart_for_slot(category, options[0], CHART_OUT_DIR)
    try:
        try:
            sent = send_manual_post_batch(category, options, image_path=chart_path)
        except Exception as e:
            return _fail(now, category, f"send_manual_post_batch raised an exception: {e!r}")

        if not sent:
            return _fail(now, category, "send_manual_post_batch returned False — email did not go out")

        print(f"[stream2] Batch emailed=True — category={category}, {len(options)} option(s), "
              f"chart={chart_path is not None}.")
        state["last_generated_at"] = now.isoformat()
        state["last_category"] = category
        save_state(state)
        return 0
    finally:
        # Always clean up, whether the email succeeded, failed, or was
        # never attempted — a chart PNG must never accumulate on disk.
        cleanup_chart(chart_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                         help="Bypass active-hours and interval checks — run right now regardless.")
    args = parser.parse_args()
    sys.exit(run(force=args.force))
