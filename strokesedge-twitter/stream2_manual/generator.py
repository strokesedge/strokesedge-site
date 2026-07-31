"""
Stream 2 — generates 2-3 phrasing options per slot, all covering the same
underlying content angle so Brian can pick the one he likes rather than
edit from scratch. No approval flow, no queue routing — every slot that
generates cleanly goes straight to emailer.py.
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

from config import TWITTER_CHAR_LIMIT, MIN_OPTIONS_PER_SLOT, MAX_OPTIONS_PER_SLOT, PICKS_URL, DISCLAIMER
from content import available_categories, next_category, build_context

SYSTEM_PROMPT = f"""You write tweets for @StrokesEdge, a PGA Tour golf betting analytics account.
This is the manually-posted stream — Brian reviews and posts these himself by
copy/paste, so every option must be ready to post as-is with no editing needed.

VOICE RULES (strict):
- Data-forward and analytical. Zero narrative betting language, zero gut feels.
- No em dashes anywhere.
- Standard sentence case. Not all-caps, not all-lowercase.
- No AI-sounding parallel structure or tidy summary sentences.
- Hard limit: 280 characters INCLUDING the link and disclaimer text. Write
  the tweet content itself (before the link) at 190-210 characters — the
  link and optional disclaimer add the rest. Any option that comes in over
  280 gets filtered out silently before Brian ever sees it, which just
  means fewer options to choose from, so leave real margin.

LINK REQUIRED — every single option must include exactly this link, as
plain text (not markdown, no brackets): {PICKS_URL}
The link alone is about 26 characters. Include "{DISCLAIMER}" (about 43
more characters) too, but ONLY if there's room left after the link and the
tweet content — never cut the link short or drop it to fit the disclaimer
in. If in doubt, leave the disclaimer out rather than risk going over 280.

CONTENT ACCURACY (non-negotiable):
- Never state a stat, player name, odds, or number not present in the
  source content given to you. Do not invent plausible-sounding details.
- If given confirmed open bets, use ONLY those exact players/odds/bet
  types — never alter, round, or reinterpret them.

TASK: Write {MIN_OPTIONS_PER_SLOT} to {MAX_OPTIONS_PER_SLOT} DIFFERENT phrasings
of the SAME underlying tweet — same core content and angle, genuinely different
wording/structure/opening so they read like distinct options, not
find-and-replace variants of each other.

OUTPUT FORMAT: Return a JSON array of strings, one per option. Nothing else,
no markdown fences, no preamble.
"""

CATEGORY_INSTRUCTIONS = {
    "course_facts": (
        "Options should share a specific course fact or analytics detail for "
        "{tournament} {year} — par, yardage, a notable hole, historical scoring, "
        "field size, or similar, pulled from the source content below."
    ),
    "methodology": (
        "Options should share a piece of how the StrokesEdge model works — an SG "
        "category and why it's weighted the way it is, or a general methodology "
        "point. Evergreen brand content, not tied to a specific pick."
    ),
    "course_fit": (
        "Options should share general course-fit commentary for {tournament} {year} "
        "— what kind of player profile suits this course/setup and why. Stat-profile "
        "commentary, not a specific bet or odds."
    ),
    "weather": (
        "Options should share the weather/conditions forecast for {tournament} {year} "
        "and how it could affect play, using only the forecast details in the source "
        "content below."
    ),
    "picks": (
        "Options should highlight the confirmed open bets for {tournament} {year} "
        "below — vary the angle across options (one could highlight a value screen "
        "edge, one a tier/category summary, one a single standout play) but every "
        "option must use only the exact players/odds given."
    ),
}


def _extract_json_array(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.M).strip()
    return json.loads(raw)


def _validate_options(options):
    """Filters to options that are postable as-is. Returns (valid_options,
    rejected_reasons) — never silently drops without a reason logged by
    the caller."""
    valid = []
    rejected = []
    for opt in options:
        if not contains_site_link(opt):
            rejected.append((opt, "missing required link"))
            continue
        if len(opt) > TWITTER_CHAR_LIMIT:
            rejected.append((opt, f"over length ({len(opt)} chars)"))
            continue
        valid.append(opt)
    return valid[:MAX_OPTIONS_PER_SLOT], rejected


def generate_slot_options(last_category, now=None):
    """Returns (category, options, error_reason). options is a list of
    MIN_OPTIONS_PER_SLOT-MAX_OPTIONS_PER_SLOT ready-to-post strings on
    success, or [] with error_reason set on failure — callers must never
    email an empty/short options list."""
    cats = available_categories(now)
    start = cats.index(next_category(last_category, now))

    for offset in range(len(cats)):
        category = cats[(start + offset) % len(cats)]
        context = build_context(category)
        if context is None:
            continue

        instruction = CATEGORY_INSTRUCTIONS[category].format(
            tournament=TOURNAMENT["name"], year=TOURNAMENT["year"]
        ) + f"\n\n{context}"

        # Higher max_tokens than the shared default: this call generates
        # 2-3 full tweet options per request instead of one, and the
        # model's 'thinking' block draws from the same budget as the
        # visible output — confirmed live 2026-07-31, the default (4000)
        # was occasionally exhausted by thinking alone on this heavier request.
        raw = call_claude(SYSTEM_PROMPT, instruction, max_tokens=6000)
        try:
            options = _extract_json_array(raw)
        except json.JSONDecodeError:
            return category, [], f"model did not return valid JSON:\n{raw}"

        valid, rejected = _validate_options(options)
        if len(valid) < MIN_OPTIONS_PER_SLOT:
            reasons = "; ".join(f"{r}" for _, r in rejected) or "model returned too few options"
            return category, [], f"only {len(valid)} valid option(s) after filtering: {reasons}"

        return category, valid, None

    return cats[start], [], "no category had usable source content this run"


if __name__ == "__main__":
    category, options, error_reason = generate_slot_options(last_category=None)
    print(f"Category: {category}")
    if error_reason:
        print(f"FAILED — {error_reason}")
    else:
        for i, opt in enumerate(options, 1):
            print(f"\n[Option {i}] ({len(opt)} chars)\n{opt}")
