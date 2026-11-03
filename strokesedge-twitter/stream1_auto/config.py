"""
Stream 1 — automatic, link-free tweet stream. Edit cadence/category knobs
here; tournament identity lives in shared/tournament_config.py since both
streams need to agree on it.
"""

import os
from datetime import datetime

QUEUE_DIR = os.path.join(os.path.dirname(__file__), "queue")
POSTED_LOG = os.path.join(QUEUE_DIR, "posted_log.jsonl")
FLAGGED_LOG = os.path.join(QUEUE_DIR, "flagged_log.jsonl")  # generator output that failed a safety check — never posted, logged for review
PLAYER_DIVERSITY_LOG = os.path.join(QUEUE_DIR, "player_diversity_log.jsonl")  # not a rejection log — records when the diversity guard regenerated or fell back, for rate visibility
CHART_FAILED_LOG = os.path.join(QUEUE_DIR, "chart_failed_log.jsonl")  # chart generation/upload failures — the post still goes out text-only, this is visibility only, never a reason to hold the slot
CHART_OUT_DIR = os.path.join(QUEUE_DIR, "charts")  # PNGs are deleted right after posting — see run_cycle.py — this dir should stay empty between runs
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
# Same ticker pattern as the legacy prototype: a scheduled task fires every
# 15 min, always, and should_run() decides whether enough time has passed.
# Standard days: ~15 posts/day across the 7am-11pm active window,
# 16h * 60 / 15 = 64 min. Tue/Wed run tighter (45 min, still divisible by
# the 15-min tick) to push more posts out on the days historically closest
# to when picks content and engagement are highest — same active-hours
# window, cadence only.
ACTIVE_START_HOUR = 7   # inclusive
ACTIVE_END_HOUR = 23    # exclusive
TARGET_POSTS_PER_DAY = 15
# Changed 2026-10-07 at Brian's request: one post every ~2 hours, every day
# (~8 posts/day across the 16h window). Tue/Wed no longer run tighter.
CADENCE_MINUTES_STANDARD = 120
CADENCE_MINUTES_TUE_WED = 120
VARIABLE_CADENCE_WEEKDAYS = (1, 2)  # Python weekday(): Tuesday=1, Wednesday=2


def cadence_minutes_for(now=None):
    """The only place cadence-by-weekday logic lives — run_cycle.py must
    call this instead of reading a flat constant, so Tue/Wed and the rest
    of the week can never drift out of sync with each other."""
    now = now or datetime.now()
    if now.weekday() in VARIABLE_CADENCE_WEEKDAYS:
        return CADENCE_MINUTES_TUE_WED
    return CADENCE_MINUTES_STANDARD

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

# Every tweet must be identifiable as being about this week's tournament
# without relying on source material the reader never sees — either the
# official hashtag or the tournament name itself must appear in the
# visible text. Hard requirement, same pattern as the checks above.
REQUIRE_TOURNAMENT_REFERENCE = True

# ── Live picks commentary (category "live_picks") ───────────────────
# Added 2026-10-07. Only exists while the tournament is in progress: shared/
# live_picks.py returns None (category unavailable) before round 1 starts,
# after the final round completes, if the Data Golf feed's event does not
# match shared/tournament_config.py, or if the published-picks article is
# missing. It compares StrokesEdge's PUBLISHED picks against live positions.
# It therefore needs a different safety net than the other categories:
# standing language and tier names are the whole point here, but odds,
# stakes, links and result claims remain forbidden, and every number in the
# tweet must appear in the source content (see generator._live_flag).
LIVE_FORBIDDEN_WORDS = [
    "odds", "+ev", "-ev", "unit", "units", "wager", "parlay", "stake",
    "bet:", "pick:", "play:", "lock", "guarantee",
    # calendar/schedule guesses: only the round number is known
    "moving day", "weekend", "thursday", "friday", "saturday", "sunday",
    "cut line", "back nine", "front nine",
]
# Past-tense/result language: positions are in progress, never outcomes.
LIVE_RESULT_PHRASES = [
    "cashed", "cashing", "cash ", "winning ticket", "ticket", "paid out", "payout",
    "lost our", "we lost", "we won", "hit our", "missed our", "profit",
]

# ── Near-duplicate detection ─────────────────────────────────────────
# Same approach and threshold as legacy_v1/queue_manager.py's
# find_near_duplicate() (stdlib difflib, no embeddings call) — 0.75 was
# chosen there as a reasonable middle ground, not empirically tuned, and
# there's no reason for stream1 to pick a different number. Window is
# smaller here (15 vs legacy's 20) since this compares against actually
# *posted* tweets, not everything ever queued.
DUPLICATE_SIMILARITY_THRESHOLD = 0.75
DUPLICATE_CHECK_WINDOW = 15

# ── Player-name diversity ─────────────────────────────────────────────
# Categories with no natural reason to name a specific player — the safe
# fallback set when a candidate keeps colliding on the same player after
# one regeneration attempt.
NO_PLAYER_CATEGORIES = ["course_facts", "methodology", "weather"]
PLAYER_DIVERSITY_LOOKBACK_POSTS = 10  # how many recent posted tweets to scan for player mentions
PLAYER_DIVERSITY_BLOCK_RECENT = 4     # block a player if they appear in this many of the most-recent lookback
