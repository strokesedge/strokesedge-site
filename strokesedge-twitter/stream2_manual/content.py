"""
Stream 2 — category rotation and source-content assembly. Deliberately not
shared with stream1_auto/content.py even though the logic looks similar —
each stream owns its own category list and its own rotation state so the
two never have to coordinate or drift into a shared dependency.
"""

import os
import sys
from datetime import datetime

_SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

from tournament_config import TOURNAMENT, SITE_REPO
from html_utils import load_local_file
from tracker import is_picks_phase, get_open_bets_for_tournament

from config import CATEGORIES_DEFAULT


def available_categories(now=None):
    cats = list(CATEGORIES_DEFAULT)
    if is_picks_phase():
        cats.append("picks")
    return cats


def next_category(last_category, now=None):
    cats = available_categories(now)
    if last_category in cats:
        idx = (cats.index(last_category) + 1) % len(cats)
    else:
        idx = 0
    return cats[idx]


def _analysis_and_course_context():
    chunks = []
    course_text = load_local_file(TOURNAMENT["course_file"], SITE_REPO)
    analysis_text = load_local_file(TOURNAMENT["analysis_file"], SITE_REPO)
    if course_text:
        chunks.append(f"COURSE GUIDE CONTENT:\n{course_text[:4000]}")
    if analysis_text:
        chunks.append(f"ANALYSIS PAGE CONTENT:\n{analysis_text[:4000]}")
    return "\n\n".join(chunks) if chunks else None


def build_context(category):
    """Returns source-content string for this category, or None if there's
    nothing usable right now (generator.py falls back to another category
    rather than let the model invent facts)."""

    if category in ("course_facts", "course_fit"):
        return _analysis_and_course_context()

    if category == "methodology":
        text = load_local_file(TOURNAMENT["methodology_file"], SITE_REPO)
        return f"METHODOLOGY PAGE CONTENT:\n{text[:4000]}" if text else None

    if category == "weather":
        text = load_local_file(TOURNAMENT["analysis_file"], SITE_REPO)
        if not text or "weather" not in text.lower():
            return None
        return f"ANALYSIS PAGE CONTENT (contains weather section):\n{text[:4000]}"

    if category == "picks":
        # ONLY valid source for player/odds content, per the site's
        # content-accuracy rule — never analysis.html once picks are live.
        bets = get_open_bets_for_tournament()
        if not bets:
            return None
        lines = [f"CONFIRMED OPEN BETS for {TOURNAMENT['name']} {TOURNAMENT['year']} "
                 f"(from tracker CSV — the ONLY valid source for player/odds, use these "
                 f"exact values, never alter or round them):"]
        for b in bets:
            lines.append(f"- {b.get('player','?')} | {b.get('type','?')} | "
                          f"odds {b.get('odds','?')}")
        return "\n".join(lines)

    return None
