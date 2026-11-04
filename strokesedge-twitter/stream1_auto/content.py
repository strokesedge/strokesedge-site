"""
Stream 1 — category rotation and source-content assembly. No prompting or
API calls here (that's generator.py) — this module answers two questions:
"what category should the next slot be" and "what source material backs
that category."
"""

import os
import sys
from datetime import datetime

_SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

from tournament_config import TOURNAMENT, SITE_REPO
from html_utils import load_local_file
from tracker import is_tournament_complete, get_settled_bets_for_tournament, summarize_final_results

from live_picks import build_live_picks_context
from market_odds import build_odds_context

from config import CATEGORIES_DEFAULT, RECAP_WEEKDAYS, POSTED_LOG

_LIVE_CONTEXT_CACHE = {}


def live_picks_context():
    """Live picks-vs-leaderboard source content, or None when the
    tournament isn't live. Fetched at most once per minute per process so
    available_categories()/build_context() agree within a single run
    without hammering the Data Golf feed."""
    now_key = datetime.now().strftime("%Y%m%d%H%M")
    if _LIVE_CONTEXT_CACHE.get("key") != now_key:
        try:
            _LIVE_CONTEXT_CACHE["value"] = build_live_picks_context()
        except Exception as e:
            print(f"[content] live picks context unavailable: {e}")
            _LIVE_CONTEXT_CACHE["value"] = None
        _LIVE_CONTEXT_CACHE["key"] = now_key
    return _LIVE_CONTEXT_CACHE["value"]


def available_categories(now=None):
    now = now or datetime.now()
    cats = list(CATEGORIES_DEFAULT)
    if now.weekday() in RECAP_WEEKDAYS and is_tournament_complete():
        cats.append("recap")
    if live_picks_context():
        cats.append("live_picks")
    return cats


def _posted_count():
    if not os.path.exists(POSTED_LOG):
        return 0
    with open(POSTED_LOG, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def next_category(last_category, now=None):
    """While the tournament is live, every other slot is live_picks
    commentary and the slots in between rotate through the normal
    categories. Outside live play it's the original round-robin. If the
    previous category isn't in today's available list (e.g. it was
    "recap" on Monday and now it's Tuesday), just starts from the top
    rather than erroring."""
    cats = available_categories(now)
    if "live_picks" in cats:
        if last_category != "live_picks":
            return "live_picks"
        base = [c for c in cats if c != "live_picks"]
        return base[_posted_count() % len(base)]
    if last_category in cats:
        idx = (cats.index(last_category) + 1) % len(cats)
    else:
        idx = 0
    return cats[idx]


def _matches_current_tournament(text):
    """Guards against shared/tournament_config.py going stale relative to
    the actual site pages (this bit us once: TOURNAMENT still said Rocket
    Classic / Detroit Golf Club while analysis.html had already been
    hand-updated to Wyndham, and the model faithfully reported Detroit's
    own real stats under a tweet that was effectively about the wrong
    week). If the page doesn't even mention this week's tournament name,
    it's not safe source content, regardless of how real its numbers are."""
    return text is not None and TOURNAMENT["name"].lower() in text.lower()


def _analysis_and_course_context():
    chunks = []
    course_text = load_local_file(TOURNAMENT["course_file"], SITE_REPO)
    analysis_text = load_local_file(TOURNAMENT["analysis_file"], SITE_REPO)
    if course_text and not _matches_current_tournament(course_text):
        course_text = None
    if analysis_text and not _matches_current_tournament(analysis_text):
        analysis_text = None
    if course_text:
        chunks.append(f"COURSE GUIDE CONTENT:\n{course_text[:4000]}")
    if analysis_text:
        chunks.append(f"ANALYSIS PAGE CONTENT:\n{analysis_text[:4000]}")
    return "\n\n".join(chunks) if chunks else None


def build_context(category):
    """Returns the source-content string to hand the model, or None if
    there's no usable source for this category right now (generator.py
    should fall back to a different category rather than let the model
    invent facts to fill the gap)."""

    if category == "course_facts":
        return _analysis_and_course_context()

    if category == "course_fit":
        return _analysis_and_course_context()

    if category == "course_conditions":
        return _analysis_and_course_context()

    if category == "odds":
        try:
            return build_odds_context()
        except Exception as e:
            print(f"[content] odds context unavailable: {e}")
            return None

    if category == "methodology":
        text = load_local_file(TOURNAMENT["methodology_file"], SITE_REPO)
        return f"METHODOLOGY PAGE CONTENT:\n{text[:4000]}" if text else None

    if category == "weather":
        # Weather content only exists on analysis.html some weeks (added
        # manually when a real forecast has been pulled in) — there's no
        # dedicated weather source. If it's not present, this category
        # has nothing to say this run; generator.py falls back rather
        # than let the model invent a forecast.
        text = load_local_file(TOURNAMENT["analysis_file"], SITE_REPO)
        if (not text or not _matches_current_tournament(text)
                or not any(k in text.lower() for k in ("weather", "wind", "forecast", "rain"))):
            return None
        return f"ANALYSIS PAGE CONTENT (contains weather section):\n{text[:4000]}"

    if category == "live_picks":
        return live_picks_context()

    if category == "recap":
        if not is_tournament_complete():
            return None
        settled = get_settled_bets_for_tournament()
        if not settled:
            return None
        summary = summarize_final_results(settled)
        lines = [f"FINAL SETTLED RECORD for {TOURNAMENT['name']} {TOURNAMENT['year']} "
                 f"(from tracker CSV, every bet now settled — this is the ONLY source of "
                 f"truth for numbers in a recap tweet):"]
        overall = summary["_overall"]
        lines.append(f"- Overall: {overall['cashed']}-for-{overall['total']} "
                      f"({overall['won']} won, {overall['placed']} placed, {overall['lost']} lost)")
        for bet_type, counts in summary.items():
            if bet_type == "_overall":
                continue
            lines.append(f"- {bet_type}: {counts['cashed']}-for-{counts['total']} "
                          f"({counts['won']} won, {counts['placed']} placed, {counts['lost']} lost)")
        return "\n".join(lines)

    return None
