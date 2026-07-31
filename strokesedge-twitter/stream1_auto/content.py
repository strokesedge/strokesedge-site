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

from config import CATEGORIES_DEFAULT, RECAP_WEEKDAYS


def available_categories(now=None):
    now = now or datetime.now()
    cats = list(CATEGORIES_DEFAULT)
    if now.weekday() in RECAP_WEEKDAYS and is_tournament_complete():
        cats.append("recap")
    return cats


def next_category(last_category, now=None):
    """Round-robins through whatever's available right now. If the
    previous category isn't in today's available list (e.g. it was
    "recap" on Monday and now it's Tuesday), just starts from the top
    rather than erroring."""
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
    """Returns the source-content string to hand the model, or None if
    there's no usable source for this category right now (generator.py
    should fall back to a different category rather than let the model
    invent facts to fill the gap)."""

    if category == "course_facts":
        return _analysis_and_course_context()

    if category == "course_fit":
        return _analysis_and_course_context()

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
        if not text or "weather" not in text.lower():
            return None
        return f"ANALYSIS PAGE CONTENT (contains weather section):\n{text[:4000]}"

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
