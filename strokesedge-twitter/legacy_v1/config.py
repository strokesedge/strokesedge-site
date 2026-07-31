"""
StrokesEdge Twitter Auto-Poster — Config

Edit TOURNAMENT settings each week. Everything else is logic, not data.
"""

import os

# ── Current tournament ──────────────────────────────────────────
# Rocket Classic 2026 — current tournament on analysis.html.
TOURNAMENT = {
    "name": "Rocket Classic",
    "year": 2026,
    "course_file": "course-detroit-golf-club.html", # dedicated course guide exists for this tournament
    "analysis_file": "analysis.html",               # permanent page, always current tournament
    "hashtag": "#RocketClassic",
}

# ── Paths ────────────────────────────────────────────────────────
# NOTE (fixed 2026-07-30): site pages live under "Strokes Edge Website HTML/",
# not the repo root directly. SITE_REPO must point there or load_local_file()
# in generator.py silently returns None for every file (os.path.join with a
# nonexistent path just fails the os.path.exists check) — the original test
# setup pointed at the repo root and would never have actually found
# analysis.html or any course file.
SITE_REPO = r"C:\Users\bkopp\strokesedge-site\Strokes Edge Website HTML"
QUEUE_DIR = os.path.join(os.path.dirname(__file__), "queue")
APPROVED_QUEUE = os.path.join(QUEUE_DIR, "approved_queue.jsonl")     # link-free only — this is what post_tweets.py auto-posts
PENDING_REVIEW = os.path.join(QUEUE_DIR, "pending_review.jsonl")
POSTED_LOG = os.path.join(QUEUE_DIR, "posted_log.jsonl")
REJECTED_LOG = os.path.join(QUEUE_DIR, "rejected_log.jsonl")
MANUAL_POST_QUEUE = os.path.join(QUEUE_DIR, "manual_post_queue.jsonl")  # link-included — Brian posts these himself
SKIPPED_DUPLICATES_LOG = os.path.join(QUEUE_DIR, "skipped_duplicates.log")
GENERATE_SCHEDULE_STATE = os.path.join(QUEUE_DIR, "generate_schedule_state.json")

# ── Link safety net (2026-07-30) ─────────────────────────────────
# X's free API tier was discontinued Feb 2026; posting now costs real money
# per tweet, and MORE if the tweet contains a link ($0.20/post-with-link vs
# $0.015/post-without, per X's pay-per-use pricing). Rather than gate cadence
# against a cap that may not even apply to this app's billing plan, the
# pipeline just never auto-posts a link via the API at all: link-free
# content auto-posts (cheap, no special handling needed); anything with the
# site link routes to manual_post_queue.jsonl for Brian to post by hand
# (free — he's not calling the API). Checked at three points: when a tweet
# is first queued (queue_manager.py), when it's approved out of
# pending_review.jsonl (approve.py), and immediately before actually calling
# the X API (post_tweets.py) as the final, hard safety net.
LINK_MARKERS = ("strokesedge.com", "picks.html")


def contains_site_link(text):
    lowered = text.lower()
    return any(marker in lowered for marker in LINK_MARKERS)


# ── Monthly auto-post budget (safety valve, not a hard API cap) ───
# Pay-per-use has no monthly cap to hit — this is a self-imposed ceiling so
# a scheduling bug can't quietly run up a real bill unattended. Comfortably
# above the calculated worst-case volume (~1063/month at full cadence, see
# the schedule math) but still a real stop rather than no limit at all.
MONTHLY_AUTO_POST_BUDGET = 1200
COST_PER_AUTO_POST = 0.015  # USD, no-link post rate

# ── Tracker CSV (authoritative source for confirmed picks) ──────
TRACKER_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRn7eBjHWBs4nag5K5QHxnKiyeC-UEobNINAfjmEKsnBgX6aqm3lEZCY1i4lg5t5Lwy3I2p8ZLrR4Gc/pub?gid=0&single=true&output=csv"

# ── Site links (standard footer) ─────────────────────────────────
PICKS_URL = "strokesedge.com/picks.html"
DISCLAIMER = "Not financial advice. Gamble responsibly."

# ── Posting cadence ───────────────────────────────────────────────
# How many tweets to generate per run. Script is meant to be run
# daily (or 2x/day) via Task Scheduler leading up to the tournament.
TWEETS_PER_RUN = 2

# ── Generation schedule (2026-07-30) ──────────────────────────────
# scheduled_generate.py fires every 15 min via Task Scheduler and decides
# for itself whether to actually generate, based on this. Active window is
# 16 hours/day (7am-11pm) — assumes an ~11pm-7am sleep window; adjust
# ACTIVE_START_HOUR/ACTIVE_END_HOUR if that's wrong for Brian's schedule.
ACTIVE_START_HOUR = 7    # inclusive
ACTIVE_END_HOUR = 23     # exclusive — so active hours are 7,8,...,22 (16 of them)

# Tue/Wed: odds go live, model content freshest, best signup window — tighter
# cadence. Every other day (including Thu-Sun tournament rounds): hourly.
# Thu-Sun is called out as its own case in the original ask even though it
# computes to the same number as the "default" case — flagged as adjustable
# later if Brian wants live-round cadence tighter than the rest of the week;
# starting at hourly rather than guessing at something more aggressive.
TIGHT_CADENCE_WEEKDAYS = (1, 2)  # Python weekday(): Monday=0 ... Tuesday=1, Wednesday=2
TIGHT_CADENCE_MINUTES = 45
DEFAULT_CADENCE_MINUTES = 60

# ── Words/phrases that trigger mandatory human review ────────────
# Any generated tweet containing one of these (case-insensitive)
# gets routed to pending_review.jsonl instead of approved_queue.jsonl,
# regardless of week phase. This is a second safety net on top of
# the phase-based routing.
REVIEW_TRIGGER_WORDS = [
    "odds", "+", "-EV", "unit", "units", "pick:", "play:", "bet:",
    "e/w", "outright winner", "top 10", "top 20", "make cut",
    "fade", "longshot", "parlay",
]
