"""
Stream 1 — tweet generation + the automated safety checks that stand in
for human review (there is no human review on this stream, by design).

generate_slot() either returns a clean tweet ready to post, or None with a
reason logged — callers (run_cycle.py) must never post on a None.
"""

import difflib
import json
import os
import re
import sys
from datetime import datetime

_SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from claude_api import call_claude
from link_check import contains_site_link
from tournament_config import TOURNAMENT
from tracker import fetch_tracker_rows
from tweet_style import POSITIVE_TONE_RULES, SEO_RULES_LINK_FREE

from config import (
    TWITTER_CHAR_LIMIT, BETTING_LANGUAGE_TRIGGER_WORDS,
    STANDING_LANGUAGE_TRIGGER_PHRASES, REQUIRE_TOURNAMENT_REFERENCE,
    DUPLICATE_SIMILARITY_THRESHOLD, DUPLICATE_CHECK_WINDOW,
    NO_PLAYER_CATEGORIES, PLAYER_DIVERSITY_LOOKBACK_POSTS,
    PLAYER_DIVERSITY_BLOCK_RECENT, PLAYER_DIVERSITY_LOG, POSTED_LOG,
    LIVE_FORBIDDEN_WORDS, LIVE_RESULT_PHRASES,
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

{POSITIVE_TONE_RULES}

{SEO_RULES_LINK_FREE.format(tournament=TOURNAMENT['name'], hashtag=TOURNAMENT['hashtag'])}

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
- Every tweet must include either the hashtag {TOURNAMENT['hashtag']} or the
  literal phrase "{TOURNAMENT['name']}" somewhere in the visible text — this
  is checked automatically after generation and anything missing both gets
  discarded, so build it into the sentence naturally rather than bolting the
  hashtag on as an afterthought.

CONTENT ACCURACY (non-negotiable):
- Never state a stat, fact, or number that is not present in the source
  content given to you. Do not fill gaps with plausible-sounding invented
  details.

OUTPUT FORMAT: Return a single tweet as plain text. Nothing else — no quotes,
no markdown, no preamble, no explanation.
"""

LIVE_SYSTEM_PROMPT = f"""You write tweets for @StrokesEdge, a PGA Tour golf analytics account.
This is the fully automatic stream, nobody reviews these before they post, so the
rules below are hard requirements.

This slot is LIVE COMMENTARY: how StrokesEdge's published model picks are
standing right now against the live leaderboard at the {TOURNAMENT['name']}.

VOICE RULES (strict):
- Data-forward and analytical. No gut feels, no hype, no emojis.
- No em dashes anywhere.
- Standard sentence case.
- No AI-sounding parallel structure or tidy summary sentences.
- Hard limit 280 characters. Target 230-250. Over 280 is discarded.

{POSITIVE_TONE_RULES}

{SEO_RULES_LINK_FREE.format(tournament=TOURNAMENT['name'], hashtag=TOURNAMENT['hashtag'])}

ABSOLUTE RULES:
- NEVER include a link or URL.
- NEVER mention odds, prices, stakes, units, wagers, tickets, profit or any
  money amount. Refer to picks only as "our pick", "the model's pick", "a
  StrokesEdge pick" or by the pick label given in the source.
- These are IN-PROGRESS positions. NEVER say a pick won, lost, cashed, hit
  or missed, and never call anything final. Describing position, score and
  holes played is fine. A player listed as having missed the cut can be
  described that way, since that is already a fact.
- Use ONLY the players, positions, scores and hole counts in the source
  content, copied exactly. Do not round, estimate, rank or add any number
  that is not in the source. Do not claim anything about who is likely to win.
- Do not guess the day of the week or schedule, use only the round number.
- Never reply to or reference another tweet or account.
- Include either the hashtag {TOURNAMENT['hashtag']} or the phrase
  "{TOURNAMENT['name']}" in the visible text, built in naturally.
- Vary the angle between tweets: best-placed pick, a pick making a move, a
  pick struggling, or how the picks compare with the current leaders.

OUTPUT FORMAT: a single tweet as plain text. Nothing else.
"""

CATEGORY_INSTRUCTIONS = {
    "live_picks": (
        "Write one live-commentary tweet comparing StrokesEdge's published picks "
        "with the current {tournament} {year} leaderboard, using only the live "
        "status below. Pick ONE angle (best-placed pick, a notable struggle, or "
        "picks versus the leaders) rather than listing everyone. Do no arithmetic and "
        "no counting of your own: any gap to the leader, count of picks, or top-10 "
        "claim must be copied from the pick lines or DERIVED FACTS below."
    ),
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


_NUMBER_WORDS = {"two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
                 "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
                 "thirteen": "13", "fourteen": "14", "fifteen": "15", "sixteen": "16",
                 "seventeen": "17", "eighteen": "18", "twenty": "20"}


def _numeric_tokens(text):
    """Digits plus spelled-out numbers (two..twenty, and 'one' only when it
    quantifies a shot/stroke gap), so 'four back' is checked like '4'."""
    lowered = text.lower()
    tokens = set(re.findall(r"\d+", text))
    for word, digit in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", lowered):
            tokens.add(digit)
    if re.search(r"\bone[- ](shot|stroke|back|off|behind)", lowered):
        tokens.add("1")
    return tokens


def _live_flag(text, context, recent_posted_texts=None):
    """Safety net for the live_picks category. Unlike _needs_flag it allows
    standing language and tier wording, but is stricter on facts: every
    number in the tweet (other than the year) must appear in the source
    content, so an invented or mis-copied score, position or hole count is
    discarded rather than posted."""
    if contains_site_link(text):
        return "contains a site link (forbidden in this stream)"
    if len(text) > TWITTER_CHAR_LIMIT:
        return f"over length ({len(text)} chars)"
    lowered = text.lower()
    for word in LIVE_FORBIDDEN_WORDS:
        if word in lowered:
            return f"contains forbidden word in live commentary: {word!r}"
    for phrase in LIVE_RESULT_PHRASES:
        if phrase in lowered:
            return f"contains result/payout language: {phrase!r}"
    if re.search(r"(?<![\w])[+-]\d{3,5}\b", text) or "$" in text:
        return "contains an odds-like or money figure"
    if REQUIRE_TOURNAMENT_REFERENCE and not _has_tournament_reference(text):
        return "missing tournament reference"
    allowed = _numeric_tokens(context) | {str(TOURNAMENT["year"])}
    unknown = _numeric_tokens(text) - allowed
    if unknown:
        return f"contains number(s) not in the live source content: {sorted(unknown)}"
    if recent_posted_texts:
        dup = _find_near_duplicate(text, recent_posted_texts)
        if dup is not None:
            return f"near-duplicate of a recently posted tweet: {dup[:80]!r}"
    return None


def _has_tournament_reference(text):
    lowered = text.lower()
    hashtag = (TOURNAMENT.get("hashtag") or "").lower()
    name = TOURNAMENT["name"].lower()
    return (hashtag and hashtag in lowered) or (name in lowered)


def _load_posted_texts(limit=None):
    if not os.path.exists(POSTED_LOG):
        return []
    with open(POSTED_LOG, "r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]
    texts = [item["text"] for item in items]
    return texts[-limit:] if limit else texts


def _find_near_duplicate(text, recent_texts):
    """Same approach as legacy_v1/queue_manager.py's find_near_duplicate()
    (stdlib difflib ratio, no embeddings call) — kept at the same 0.75
    threshold for consistency rather than picking a new number."""
    for existing in recent_texts:
        ratio = difflib.SequenceMatcher(None, text.lower(), existing.lower()).ratio()
        if ratio >= DUPLICATE_SIMILARITY_THRESHOLD:
            return existing
    return None


def _needs_flag(text, recent_posted_texts=None):
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
    if REQUIRE_TOURNAMENT_REFERENCE and not _has_tournament_reference(text):
        return (f"missing tournament reference (neither {TOURNAMENT.get('hashtag')!r} "
                f"nor {TOURNAMENT['name']!r} appears in visible text)")
    if recent_posted_texts:
        dup = _find_near_duplicate(text, recent_posted_texts)
        if dup is not None:
            return f"near-duplicate of a recently posted tweet: {dup[:80]!r}"
    return None


def _get_player_list():
    """Player names for this tournament, from the tracker CSV — the same
    source both streams already treat as the only source of truth for
    player names (see shared/tracker.py). Used only to detect which player
    (if any) a candidate tweet is primarily about; failing to fetch just
    means the diversity check can't run this slot, not a posting failure."""
    try:
        rows = fetch_tracker_rows()
        names = {
            (row.get("player") or "").strip()
            for row in rows
            if TOURNAMENT["name"].lower() in (row.get("tournament") or "").strip().lower()
        }
        return sorted(n for n in names if n)
    except Exception as e:
        print(f"[generator] Could not fetch player list for diversity check, skipping it this slot: {e}")
        return []


def _primary_player_mention(text, player_list):
    """Longest matching name wins, so a full "Cameron Young" match isn't
    shadowed by a shorter unrelated name that happens to be a substring."""
    matches = [p for p in player_list if p.lower() in text.lower()]
    return max(matches, key=len) if matches else None


def _recent_posted_players(player_list, lookback=PLAYER_DIVERSITY_LOOKBACK_POSTS):
    recent_texts = _load_posted_texts(limit=lookback)
    return [_primary_player_mention(t, player_list) for t in recent_texts]


def _log_diversity_event(category, text, player, action):
    os.makedirs(os.path.dirname(PLAYER_DIVERSITY_LOG), exist_ok=True)
    with open(PLAYER_DIVERSITY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "category": category, "text": text, "player": player,
            "action": action, "at": datetime.now().isoformat(),
        }) + "\n")


def _generate_for_category(category, context, recent_posted_texts):
    instruction = CATEGORY_INSTRUCTIONS[category].format(
        tournament=TOURNAMENT["name"], year=TOURNAMENT["year"]
    ) + f"\n\n{context}"

    if category == "live_picks":
        raw = call_claude(LIVE_SYSTEM_PROMPT, instruction).strip()
        raw = re.sub(r'^"|"$', "", raw).strip()
        return raw, _live_flag(raw, context, recent_posted_texts)

    raw = call_claude(SYSTEM_PROMPT, instruction).strip()
    raw = re.sub(r'^"|"$', "", raw).strip()

    return raw, _needs_flag(raw, recent_posted_texts)


def generate_slot(last_category, now=None):
    """Picks the next category, builds context, generates a tweet, and
    runs it through the automated safety net (link, length, betting
    language, standing language, tournament reference, near-duplicate),
    plus a player-name diversity guard.

    Returns (category, text, flag_reason). If flag_reason is not None,
    text may still be populated (for the flag log) but must NEVER be
    posted. If context for the chosen category (and every other available
    category, in order) is unavailable, category is the last one tried and
    text is None.
    """
    cats = available_categories(now)
    start = cats.index(next_category(last_category, now))
    recent_posted_texts = _load_posted_texts(limit=DUPLICATE_CHECK_WINDOW)

    player_list = _get_player_list()
    recent_players = _recent_posted_players(player_list)
    blocked_players = {p for p in recent_players[-PLAYER_DIVERSITY_BLOCK_RECENT:] if p}

    # Try categories in rotation order starting from the intended next one,
    # falling back if a category has no usable source content this run
    # (e.g. "weather" with no forecast on the page this week) rather than
    # let the model invent facts to fill the gap.
    for offset in range(len(cats)):
        category = cats[(start + offset) % len(cats)]
        context = build_context(category)
        if context is None:
            continue

        raw, flag_reason = _generate_for_category(category, context, recent_posted_texts)
        if flag_reason:
            return category, raw, flag_reason

        primary = _primary_player_mention(raw, player_list)
        if not (primary and primary in blocked_players):
            return category, raw, None

        # Same player as a recent post — regenerate once before giving up
        # the slot to it entirely.
        _log_diversity_event(category, raw, primary, "regenerating")
        retry_raw, retry_flag_reason = _generate_for_category(category, context, recent_posted_texts)
        retry_primary = _primary_player_mention(retry_raw, player_list) if not retry_flag_reason else primary
        if not retry_flag_reason and retry_primary not in blocked_players:
            return category, retry_raw, None

        # Regeneration still collides on a player (or itself got flagged
        # for something else) — fall back to a no-player category for this
        # slot rather than post a repeat player.
        _log_diversity_event(category, retry_raw, retry_primary, "falling back to no-player category")
        for fallback in NO_PLAYER_CATEGORIES:
            if fallback == category or fallback not in cats:
                continue
            fb_context = build_context(fallback)
            if fb_context is None:
                continue
            fb_raw, fb_flag_reason = _generate_for_category(fallback, fb_context, recent_posted_texts)
            return fallback, fb_raw, fb_flag_reason

        # No no-player category had usable context either this run —
        # better to post the original (it already passed every hard check)
        # than lose the slot entirely.
        return category, raw, None

    return cats[start], None, "no category had usable source content this run"


if __name__ == "__main__":
    category, text, flag_reason = generate_slot(last_category=None)
    print(f"Category: {category}")
    if text is None:
        print(f"NOTHING GENERATED — {flag_reason}")
    else:
        print(f"({len(text)} chars) flag={flag_reason}\n{text}")
