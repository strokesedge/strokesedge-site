"""
Stream 2 — generates 2-3 phrasing options for the hourly picks-vs-live-
standings update. Reuses generator.py's JSON-array parsing and per-option
validation (link required, 280-char limit) rather than duplicating them —
the output contract is identical, only the source content and prompt
differ.
"""

import json
import os
import sys

_SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from claude_api import call_claude
from tournament_config import TOURNAMENT

from config import PICKS_URL, DISCLAIMER, MIN_OPTIONS_PER_SLOT, MAX_OPTIONS_PER_SLOT
from generator import _extract_json_array, _validate_options
from standings_content import build_standings_context

CATEGORY = "picks_vs_standings"

SYSTEM_PROMPT = f"""You write tweets for @StrokesEdge, a PGA Tour golf betting analytics account.
This is the manually-posted stream — Brian reviews and posts these himself by
copy/paste, so every option must be ready to post as-is with no editing needed.

This specific slot reports how StrokesEdge's OPEN picks are doing RIGHT NOW
against the live leaderboard, mid-tournament. This is a live-progress update,
never a final result.

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
- Never state a player name, position, score, hole count, odds, or bet
  type not present in the source content given to you. Do not invent or
  estimate a number.
- These are IN-PROGRESS live positions, not final results. NEVER say a
  bet "won," "lost," "cashed," "hit," or similar past-tense result
  language, no matter how good or bad the current position looks — only
  describe where the player currently stands (position, score to par,
  holes played).
- Don't add schedule/timing framing that isn't directly given (e.g.
  "heading into the weekend," "final round Sunday") unless the round
  number in the source content actually supports it — the round number
  alone doesn't tell you the day, and guessing one that's wrong is a
  factual error just like a wrong score.

TASK: Write {MIN_OPTIONS_PER_SLOT} to {MAX_OPTIONS_PER_SLOT} DIFFERENT phrasings
of the SAME underlying tweet — same core content and angle, genuinely different
wording/structure/opening so they read like distinct options, not
find-and-replace variants of each other.

OUTPUT FORMAT: Return a JSON array of strings, one per option. Nothing else,
no markdown fences, no preamble.
"""

INSTRUCTION_TEMPLATE = (
    "Options should compare the confirmed open picks below against their CURRENT live "
    "position in this week's {tournament} {year}, sourced from a live leaderboard feed. "
    "Vary the angle across options (one could spotlight the best-placed pick, one could "
    "give a quick spread across all live picks, one could focus on a pick in danger of "
    "missing its tier) but every option must use only the exact positions/scores given "
    "below — never estimate, round, or invent a value, and never claim a bet has won, "
    "lost, or cashed."
)


def generate_standings_options():
    """Returns (options, error_reason). options is a list of
    MIN_OPTIONS_PER_SLOT-MAX_OPTIONS_PER_SLOT ready-to-post strings on
    success, or [] with error_reason set on failure — callers must never
    email an empty/short options list."""
    context = build_standings_context()
    if context is None:
        return [], "no live standings data matched for any open pick this run"

    instruction = INSTRUCTION_TEMPLATE.format(
        tournament=TOURNAMENT["name"], year=TOURNAMENT["year"]
    ) + f"\n\n{context}"

    raw = call_claude(SYSTEM_PROMPT, instruction, max_tokens=6000)
    try:
        options = _extract_json_array(raw)
    except json.JSONDecodeError:
        return [], f"model did not return valid JSON:\n{raw}"

    valid, rejected = _validate_options(options)
    if len(valid) < MIN_OPTIONS_PER_SLOT:
        reasons = "; ".join(f"{r}" for _, r in rejected) or "model returned too few options"
        return [], f"only {len(valid)} valid option(s) after filtering: {reasons}"

    return valid, None


if __name__ == "__main__":
    options, error_reason = generate_standings_options()
    if error_reason:
        print(f"FAILED — {error_reason}")
    else:
        for i, opt in enumerate(options, 1):
            print(f"\n[Option {i}] ({len(opt)} chars)\n{opt}")
