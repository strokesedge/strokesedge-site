"""
Stream 2 — drafted, link-included tweet stream. Edit cadence/category
knobs here; tournament identity lives in shared/tournament_config.py since
both streams need to agree on it.
"""

import os

QUEUE_DIR = os.path.join(os.path.dirname(__file__), "queue")
SENT_LOG = os.path.join(QUEUE_DIR, "sent_log.jsonl")  # every batch emailed to Brian, for audit/dedup context only — nothing here gates posting, he posts by hand
FAILED_LOG = os.path.join(QUEUE_DIR, "failed_log.jsonl")  # slots that failed generation/validation — never emailed, logged so failures don't vanish silently
CHART_OUT_DIR = os.path.join(QUEUE_DIR, "charts")  # PNGs are deleted right after the email send attempt — see run_cycle.py — this dir should stay empty between runs
GENERATE_SCHEDULE_STATE = os.path.join(QUEUE_DIR, "generate_schedule_state.json")

# ── Picks-vs-live-standings updates (standings_cycle.py) ─────────────
# Separate schedule state file and cadence from the main category
# rotation above — this runs hourly, gated on shared.tracker.is_picks_phase()
# and a live leaderboard match, not on the 90-minute category ticker.
STANDINGS_SCHEDULE_STATE = os.path.join(QUEUE_DIR, "standings_schedule_state.json")
STANDINGS_CADENCE_MINUTES = 60

# ── Content categories ─────────────────────────────────────────────
# Same base categories as Stream 1, plus "picks" — added only once the
# tracker shows open bets for the current tournament (shared.tracker.
# is_picks_phase()), and sourced ONLY from the tracker CSV, never
# analysis.html, per the site's existing content-accuracy rule.
CATEGORIES_DEFAULT = ["course_facts", "methodology", "course_fit", "weather"]

# ── Link / disclaimer (every option in every batch includes these) ───
PICKS_URL = "strokesedge.com/picks.html"
DISCLAIMER = "Not financial advice. Gamble responsibly."

# ── Delivery cadence ───────────────────────────────────────────────
# ~10 batches/day, delivered by email as each is generated (not one daily
# digest). Same 7am-11pm active window as Stream 1, same every-15-min
# ticker pattern. 90 minutes gives 10-11 batches across the 16h window —
# a cleaner number than the exact 96-minute division of 16h/10, and still
# lands on "~10/day" as asked. Adjust here if Brian wants them denser or
# sparser.
ACTIVE_START_HOUR = 7   # inclusive
ACTIVE_END_HOUR = 23    # exclusive
CADENCE_MINUTES = 90

TWITTER_CHAR_LIMIT = 280
MIN_OPTIONS_PER_SLOT = 2
MAX_OPTIONS_PER_SLOT = 3
