"""
StrokesEdge Twitter Auto-Poster — Scheduled generation (variable cadence)

Task Scheduler fires this every 15 minutes, always. This script decides for
itself, each time, whether it's actually time to generate — the schedule
lives in code (config.py), not in Task Scheduler trigger XML, because "45
minutes on Tue/Wed, 60 minutes every other day, 16-hour active window" isn't
something a single Windows trigger can express cleanly. A 15-minute tick
divides evenly into both 45 and 60 minutes, so neither cadence drifts.

Logic per firing:
1. Is the current local hour within the active window (config.
   ACTIVE_START_HOUR..ACTIVE_END_HOUR)? If not, exit quietly.
2. What's today's interval — TIGHT_CADENCE_MINUTES (Tue/Wed) or
   DEFAULT_CADENCE_MINUTES (every other day, including Thu-Sun tournament
   rounds — see config.py for why those compute to the same number)?
3. Has at least that many minutes passed since the last generation
   (persisted in generate_schedule_state.json)? If not, exit quietly.
4. Otherwise, call queue_manager.run() and record now as the last-generated
   timestamp.

--force bypasses both the active-hours and interval checks (manual/test
trigger). --simulate-weekday=N overrides which weekday's cadence to apply
without needing to wait for an actual Tuesday/Wednesday to verify the
switch — both are for testing, not for real scheduled firings.
"""

import argparse
import json
import os
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from config import (
    ACTIVE_START_HOUR, ACTIVE_END_HOUR, TIGHT_CADENCE_WEEKDAYS,
    TIGHT_CADENCE_MINUTES, DEFAULT_CADENCE_MINUTES, GENERATE_SCHEDULE_STATE,
)
import queue_manager


def load_state():
    if os.path.exists(GENERATE_SCHEDULE_STATE):
        with open(GENERATE_SCHEDULE_STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_generated_at": None}


def save_state(state):
    os.makedirs(os.path.dirname(GENERATE_SCHEDULE_STATE), exist_ok=True)
    with open(GENERATE_SCHEDULE_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def interval_for_weekday(weekday):
    """weekday: Python convention, Monday=0 ... Sunday=6."""
    return TIGHT_CADENCE_MINUTES if weekday in TIGHT_CADENCE_WEEKDAYS else DEFAULT_CADENCE_MINUTES


def in_active_window(now):
    return ACTIVE_START_HOUR <= now.hour < ACTIVE_END_HOUR


def should_generate(now, state, interval_minutes):
    last = state.get("last_generated_at")
    if not last:
        return True
    elapsed_minutes = (now - datetime.fromisoformat(last)).total_seconds() / 60
    return elapsed_minutes >= interval_minutes


def run(force=False, simulate_weekday=None):
    now = datetime.now()
    weekday = simulate_weekday if simulate_weekday is not None else now.weekday()
    interval = interval_for_weekday(weekday)
    weekday_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][weekday]

    if not force and not in_active_window(now):
        print(f"[scheduled_generate] {now.isoformat(timespec='minutes')} — outside active hours "
              f"({ACTIVE_START_HOUR}:00-{ACTIVE_END_HOUR}:00), skipping.")
        return

    state = load_state()

    if not force and not should_generate(now, state, interval):
        last = state.get("last_generated_at")
        elapsed = (now - datetime.fromisoformat(last)).total_seconds() / 60 if last else None
        print(f"[scheduled_generate] {now.isoformat(timespec='minutes')} — {weekday_name} cadence is "
              f"{interval} min, only {elapsed:.0f} min since last generation, skipping.")
        return

    print(f"[scheduled_generate] {now.isoformat(timespec='minutes')} — {weekday_name}, "
          f"{interval}-min cadence{' (forced)' if force else ''} — generating now.")
    queue_manager.run()

    state["last_generated_at"] = now.isoformat()
    save_state(state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                         help="Bypass active-hours and interval checks — generate right now regardless.")
    parser.add_argument("--simulate-weekday", type=int, default=None, metavar="0-6",
                         help="Pretend today is this weekday (0=Monday...6=Sunday) for cadence "
                              "purposes only, without waiting for an actual Tue/Wed. Testing aid.")
    args = parser.parse_args()
    run(force=args.force, simulate_weekday=args.simulate_weekday)
