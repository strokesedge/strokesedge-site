"""
Stream 1 — automatic, link-free tweet stream. Edit cadence/category knobs
here; tournament identity lives in shared/tournament_config.py since both
streams need to agree on it.
"""

import os

QUEUE_DIR = os.path.join(os.path.dirname(__file__), "queue")
POSTED_LOG = os.path.join(QUEUE_DIR, "posted_log.jsonl")
FLAGGED_LOG = os.path.join(QUEUE_DIR, "flagged_log.jsonl")  # generator output that failed a safety check — never posted, logged for review
GENERATE_SCHEDULE_STATE = os.path.join(QUEUE_DIR, "generate_schedule_state.json")

# ── Content categories ─────────────────────────────────────────────
# No picks/odds content ever — this stream never touches the tracker's
# open-bet data. "recap" is the one category that touches the tracker at
# all, and only settled (non-open) rows.
CATEGORIES_DEFAULT = ["course_facts", "methodology", "course_fit", "weather"]
# Recap only runs Sunday evening through Monday, and only once
# shared.tracker.is_tournament_complete() confirms every bet for the
# tournament has settled — see content.py. Wed-Sat deliberately has no
# recap and no standing content: there's no live-leaderboard data source
# wired in right now, so any in-progress position would be a guess. Flag
# to Brian if a real leaderboard feed should be scoped out later.
RECAP_WEEKDAYS = (6, 0)  # Python weekday(): Sunday=6, Monday=0

# ── Posting cadence ──────────────────────────────────────────────────
# ~15 posts/day spread across a 7am-11pm active window, same ticker
# pattern as the legacy prototype: a scheduled task fires every 15 min and
# this decides whether enough time has passed. 16h * 60 / 15 = 64 min.
ACTIVE_START_HOUR = 7   # inclusive
ACTIVE_END_HOUR = 23    # exclusive
TARGET_POSTS_PER_DAY = 15
CADENCE_MINUTES = (ACTIVE_END_HOUR - ACTIVE_START_HOUR) * 60 // TARGET_POSTS_PER_DAY  # 64

# ── Cost / budget safety valve ────────────────────────────────────────
# Self-imposed ceiling, not an X-enforced cap (pay-per-use has no monthly
# cap) — exists so a scheduling bug can't quietly run up a real bill
# unattended. ~15/day * 31 days = 465 worst case; budget set comfortably
# above that.
COST_PER_AUTO_POST = 0.015  # USD, no-link post rate
MONTHLY_AUTO_POST_BUDGET = 600

TWITTER_CHAR_LIMIT = 280

# ── Automated safety net (NO human ever reviews this stream) ─────────
# Stream 1 posts itself with nobody in the loop, so every generated tweet
# gets checked against these before post_tweets.py is even allowed to see
# it. Anything that trips one of these is discarded and logged to
# FLAGGED_LOG rather than posted — see generator.py's needs_review().
#
# Betting/pick language should never appear at all: this stream's
# categories never cover picks or odds, so any of these words showing up
# means the model drifted off-brief.
BETTING_LANGUAGE_TRIGGER_WORDS = [
    "odds", "+ev", "-ev", "unit", "units", "pick:", "play:", "bet:",
    "e/w", "each-way", "outright winner", "top 10", "top 20", "top 40",
    "make cut", "fade", "longshot", "parlay", "wager",
]
# In-progress standing language should never appear either — there's no
# live leaderboard source wired in, so any tweet that implies real-time
# position data is a guess, even during the recap category (which must
# only describe a FINAL settled record, not "currently").
STANDING_LANGUAGE_TRIGGER_PHRASES = [
    "leaderboard", "currently sits", "currently sit", "co-leads", "co-lead",
    "trails by", "trailing by", "leads by", "through 36 holes",
    "through 54 holes", "through the turn", "after round", "live look",
    "right now he", "as of this writing",
]
