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

Exit code contract (audited 2026-08-05 after the identical pattern caused
a silent 0x0-while-nothing-happened failure in stream2_manual/run_cycle.py):
this process exits 0 only when either (a) it correctly did nothing because
it wasn't yet time to run, (b) it posted, (c) it hit a recognized/logged
safety-net rejection (flag_reason — see FLAGGED_LOG, this is normal
operation, not a malfunction), or (d) post_if_safe() returned False for a
reason it already logged/emailed itself (link check, budget cap, X API
error — see post_tweets.py). Any exception escaping generate_slot() or
post_if_safe() — e.g. a missing/invalid credential raised by get_client()
before post_if_safe's own try/except even starts — now writes to
FLAGGED_LOG, sends a best-effort failure email, and exits 1 so Task
Scheduler's Last Run Result actually reflects it, instead of being caught,
print()-ed, and silently treated as success.

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
    ACTIVE_START_HOUR, ACTIVE_END_HOUR, GENERATE_SCHEDULE_STATE, FLAGGED_LOG,
    CHART_OUT_DIR, cadence_minutes_for,
)
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
    return elapsed_minutes >= cadence_minutes_for(now)


def _fail(now, category, reason):
    """The one place a failed run reports itself. Writes a real FLAGGED_LOG
    entry (never just print()), best-effort emails a heads-up — send_email
    already fails safe and never raises, so this can't itself become a
    second silent failure — and returns the exit code the caller must
    propagate to sys.exit(). last_generated_at is deliberately NOT updated
    on this path: leaving it stale means the very next scheduled tick (15
    min later) simply tries again, rather than waiting out a full cadence
    interval for a slot that never actually ran."""
    print(f"[stream1] FAILURE: {reason}")
    append_jsonl(FLAGGED_LOG, {
        "category": category, "text": None, "reason": reason, "flagged_at": now.isoformat(),
    })
    send_email(
        "StrokesEdge Stream 1: scheduled run failed",
        f"A Stream 1 scheduled run failed this slot — nothing was generated or posted.\n\n"
        f"Category: {category}\nReason: {reason}\n\n"
        f"Logged to flagged_log.jsonl. This process is also exiting non-zero so Task "
        f"Scheduler's Last Run Result reflects the failure directly — treat that as "
        f"the authoritative signal, since if GMAIL_APP_PASSWORD itself is what's "
        f"broken, this email may not arrive either.",
    )
    return 1


def run(force=False, dry_run=False):
    now = datetime.now()

    if not force and not in_active_window(now):
        print(f"[stream1] {now.isoformat(timespec='minutes')} — outside active hours "
              f"({ACTIVE_START_HOUR}:00-{ACTIVE_END_HOUR}:00), skipping.")
        return 0

    state = load_state()

    if not force and not should_run(now, state):
        last = state.get("last_generated_at")
        elapsed = (now - datetime.fromisoformat(last)).total_seconds() / 60 if last else None
        print(f"[stream1] {now.isoformat(timespec='minutes')} — cadence is {cadence_minutes_for(now)} min, "
              f"only {elapsed:.0f} min since last slot, skipping.")
        return 0

    last_category = state.get("last_category")
    try:
        category, text, flag_reason = generate_slot(last_category=last_category, now=now)
    except Exception as e:
        return _fail(now, last_category, f"generation raised an exception: {e!r}")

    if flag_reason:
        append_jsonl(FLAGGED_LOG, {
            "category": category, "text": text, "reason": flag_reason,
            "flagged_at": now.isoformat(),
        })
        print(f"[stream1] Slot flagged, NOT posted — category={category}, reason={flag_reason}")
    else:
        # Chart generation is best-effort and category/content-gated
        # (course_facts/methodology/course_fit only, and only when the
        # text is actually dense enough in chartable data — see
        # chart_gen.should_chart). generate_chart_for_slot() never raises;
        # (None, None) means "no chart this slot," which is the normal,
        # expected outcome most of the time, not a failure.
        chart_path, chart_alt_text = generate_chart_for_slot(category, text, CHART_OUT_DIR)
        try:
            try:
                posted = post_if_safe(category, text, dry_run=dry_run,
                                       image_path=chart_path, alt_text=chart_alt_text)
            except Exception as e:
                return _fail(now, category, f"post_if_safe raised an exception: {e!r}")
            if not posted and not dry_run:
                # post_if_safe already logged its own reason (link check,
                # budget cap, X API error, or a chart-upload failure that
                # fell back to text-only all self-log/self-email inside
                # post_tweets.py) — this is just a console breadcrumb, not
                # a second failure report.
                print(f"[stream1] Not posted this slot — see flagged_log.jsonl for why.")
        finally:
            # Always clean up, whether the post succeeded, failed, or
            # never ran (e.g. dry-run) — a chart PNG must never accumulate
            # on disk regardless of how this slot ended.
            cleanup_chart(chart_path)

    state["last_generated_at"] = now.isoformat()
    state["last_category"] = category
    save_state(state)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                         help="Bypass active-hours and interval checks — run right now regardless.")
    parser.add_argument("--dry-run", action="store_true",
                         help="Generate and run safety checks, but don't actually call the X API.")
    args = parser.parse_args()
    sys.exit(run(force=args.force, dry_run=args.dry_run))
