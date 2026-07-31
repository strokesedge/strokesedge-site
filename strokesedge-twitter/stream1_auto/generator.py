"""
Stream 1 — tweet generation + the automated safety checks that stand in
for human review (there is no human review on this stream, by design).

generate_slot() either returns a clean tweet ready to post, or None with a
reason logged — callers (run_cycle.py) must never post on a None.
"""

import json
import os
import re
import sys

_SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from claude_api import call_claude
from link_check import contains_site_link
from tournament_config import TOURNAMENT

from config import (
    TWITTER_CHAR_LIMIT, BETTING_LANGUAGE_TRIGGER_WORDS,
    STANDING_LANGUAGE_TRIGGER_PHRASES,
)
from content import available_categories, next_category, build_context

SYSTEM_PROMPT = f"""You write tweets for @StrokesEdge, a PGA Tour golf betting analytics account.
This is the fully automatic stream — nobody reviews these before they post, so the
rules below are hard requirements, not suggestions.

VOICE RULES (strict):
- Data-forward and analytical. Zero narrative betting language, zero gut feels.
- No em dashes anywhere.
- Standard sentence case. Not all-caps, not all-lowercase.
- No AI-sounding parallel structure or tidy summary sentences.
- Hard limit: 280 characters total. Target 230-250 characters, well under
  that limit — nobody reviews this stream before it posts, so anything that
  comes in over 280 gets discarded outright rather than trimmed, and that's
  a wasted slot. Leave real margin rather than writing right up to the edge.

ABSOLUTE RULES FOR THIS STREAM:
- NEVER include a link or URL of any kind, not strokesedge.com, not picks.html,
  nothing. You may mention "StrokesEdge" by name as plain text, just never as
  or with a link.
- NEVER mention odds, a specific bet, a pick, a tier (E/W, top 10, top 20,
  fade, longshot, etc.), or any wagering language. This stream never covers
  picks content.
- NEVER state or imply a live, in-progress tournament standing (leaderboard
  position, "currently sits", "through 36 holes," etc.) — there is no live
  leaderboard data source wired into this pipeline. If writing a recap,
  describe ONLY the final settled record given to you in the source content,
  using its exact numbers.
- Never reply to or reference another tweet or account. This account only
  posts standalone tweets.

CONTENT ACCURACY (non-negotiable):
- Never state a stat, fact, or number that is not present in the source
  content given to you. Do not fill gaps with plausible-sounding invented
  details.

OUTPUT FORMAT: Return a single tweet as plain text. Nothing else — no quotes,
no markdown, no preamble, no explanation.
"""

CATEGORY_INSTRUCTIONS = {
    "course_facts": (
        "Write one tweet with a specific course fact or analytics detail for "
        "{tournament} {year} — par, yardage, a notable hole, historical scoring "
        "average, field size, or similar. Pull the specific number or detail "
        "from the source content below; do not generalize it away."
    ),
    "methodology": (
        "Write one tweet explaining a piece of how the StrokesEdge model works — "
        "an SG category and why it's weighted the way it is, or a general "
        "methodology point. This is evergreen brand/methodology content, not tied "
        "to a specific pick."
    ),
    "course_fit": (
        "Write one tweet with general course-fit commentary for {tournament} {year} "
        "— what kind of player profile or skill set suits this course/setup and why. "
        "Do not name a specific bet, odds, or tier — stat-profile commentary only."
    ),
    "weather": (
        "Write one tweet about the weather or playing-conditions forecast for "
        "{tournament} {year} and how it could affect play, using only the forecast "
        "details present in the source content below."
    ),
    "recap": (
        "Write one tweet recapping {tournament} {year} now that it's over, stating "
        "the final settled record using ONLY the exact numbers given below (e.g. "
        "\"went 3-for-8 on E/W plays this week\" — mirror that style but use the "
        "real numbers provided, not the example). Do not describe anything as "
        "in-progress; this is a look-back at a finished week."
    ),
}


def _needs_flag(text):
    """Returns a reason string if this tweet fails an automated check, else
    None. Every one of these is a hard stop, not a warning — see
    generate_slot()."""
    if contains_site_link(text):
        return "contains a site link (forbidden in this stream)"
    if len(text) > TWITTER_CHAR_LIMIT:
        return f"over length ({len(text)} chars)"
    lowered = text.lower()
    for word in BETTING_LANGUAGE_TRIGGER_WORDS:
        if word in lowered:
            return f"contains betting-language trigger word: {word!r}"
    for phrase in STANDING_LANGUAGE_TRIGGER_PHRASES:
        if phrase in lowered:
            return f"contains in-progress standing language: {phrase!r}"
    return None


def generate_slot(last_category, now=None):
    """Picks the next category, builds context, generates a tweet, and
    runs it through the automated safety net.

    Returns (category, text, flag_reason). If flag_reason is not None,
    text may still be populated (for the flag log) but must NEVER be
    posted. If context for the chosen category (and every other available
    category, in order) is unavailable, category is the last one tried and
    text is None.
    """
    cats = available_categories(now)
    start = cats.index(next_category(last_category, now))

    # Try categories in rotation order starting from the intended next one,
    # falling back if a category has no usable source content this run
    # (e.g. "weather" with no forecast on the page this week) rather than
    # let the model invent facts to fill the gap.
    for offset in range(len(cats)):
        category = cats[(start + offset) % len(cats)]
        context = build_context(category)
        if context is None:
            continue

        instruction = CATEGORY_INSTRUCTIONS[category].format(
            tournament=TOURNAMENT["name"], year=TOURNAMENT["year"]
        ) + f"\n\n{context}"

        raw = call_claude(SYSTEM_PROMPT, instruction).strip()
        raw = re.sub(r'^"|"$', "", raw).strip()

        flag_reason = _needs_flag(raw)
        return category, raw, flag_reason

    return cats[start], None, "no category had usable source content this run"


if __name__ == "__main__":
    category, text, flag_reason = generate_slot(last_category=None)
    print(f"Category: {category}")
    if text is None:
        print(f"NOTHING GENERATED — {flag_reason}")
    else:
        print(f"({len(text)} chars) flag={flag_reason}\n{text}")
