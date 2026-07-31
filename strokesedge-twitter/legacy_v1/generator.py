"""
StrokesEdge Twitter Auto-Poster — Tweet generator

Pulls source content (course guide + analysis.html early week, or
tracker open bets once picks are live), then calls the Claude API
to draft tweets in the StrokesEdge voice.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime

# Windows console codepage (cp1252) can't print arbitrary Unicode (e.g. an
# arrow in a tracker note like "boosted 170→255") — degrade to '?' instead
# of crashing rather than risk approve.py dying mid-list of pending tweets.
# Same fix already applied in weekly_course_update.py / weekly_model_pipeline.py.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from config import (
    TOURNAMENT, SITE_REPO, PICKS_URL, DISCLAIMER,
    TWEETS_PER_RUN, REVIEW_TRIGGER_WORDS, contains_site_link,
)
from tracker import is_picks_phase, get_open_bets_for_tournament

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5"  # was "claude-sonnet-4-6" (not a real model id) — fixed 2026-07-30, never actually tested before now


def strip_html(raw_html):
    """Crude tag strip — good enough for feeding body text to the model as context."""
    text = re.sub(r"<script.*?</script>", "", raw_html, flags=re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_local_file(filename):
    path = os.path.join(SITE_REPO, filename)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return strip_html(f.read())


def build_early_week_context():
    """Course guide + analysis.html content, whatever exists."""
    chunks = []
    course_text = load_local_file(TOURNAMENT["course_file"]) if TOURNAMENT["course_file"] else None
    if course_text:
        chunks.append(f"COURSE GUIDE CONTENT:\n{course_text[:4000]}")
    else:
        chunks.append(
            f"NOTE: No course guide file exists yet for {TOURNAMENT['name']} "
            f"({TOURNAMENT['course_file']} not found). Use general knowledge of "
            f"the course/tournament plus analysis.html content only. Do not "
            f"invent specific stats that aren't in the source content."
        )

    analysis_text = load_local_file(TOURNAMENT["analysis_file"])
    if analysis_text:
        chunks.append(f"ANALYSIS PAGE CONTENT:\n{analysis_text[:4000]}")

    return "\n\n".join(chunks)


def build_picks_phase_context():
    """Confirmed open bets from the tracker CSV — the only allowed source for picks."""
    bets = get_open_bets_for_tournament()
    lines = []
    for b in bets:
        lines.append(
            f"- {b.get('player','?')} | {b.get('type','?')} | "
            f"odds {b.get('odds','?')} | tournament {b.get('tournament','?')}"
        )
    return "CONFIRMED OPEN BETS (from tracker — the ONLY valid source for player/odds):\n" + "\n".join(lines)


def call_claude(system_prompt, user_prompt):
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set.")

    payload = {
        # 1000 (original) was too small: this model's 'thinking' block draws
        # from the SAME max_tokens budget as the 'text' output, and with a
        # real-sized prompt (course guide + analysis.html, ~8000 chars) it
        # consumed all 1000 tokens on thinking alone (stop_reason=max_tokens,
        # 1000/1000 thinking_tokens, zero text) — confirmed live 2026-07-30,
        # this is why the JSON parse was failing on an empty string. Same
        # failure mode already documented and fixed the same way in
        # weekly-model/weekly_model_pipeline.py.
        "model": MODEL,
        "max_tokens": 4000,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data.get("stop_reason") == "max_tokens":
        raise RuntimeError(
            "Claude call hit max_tokens before finishing (likely all budget spent on "
            "'thinking' with none left for output text) — raise max_tokens rather than "
            "trust a possibly-truncated response."
        )

    text_parts = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
    return "\n".join(text_parts)


SYSTEM_PROMPT = f"""You write tweets for @StrokesEdge, a PGA Tour golf betting analytics account.

VOICE RULES (strict):
- Data-forward and analytical. Zero narrative betting language, zero gut feels.
- No em dashes anywhere.
- Standard sentence case. Not all-caps, not all-lowercase.
- No AI-sounding parallel structure or tidy summary sentences.
- Vary rhythm across tweets: at least one should have an abrupt transition,
  a trailing-off thought, or a sudden shift from a long clause to a short one.
- Hard limit: 280 characters INCLUDING the URL and disclaimer, on any tweet
  that includes them (see per-request instructions below for exactly when
  a link is or isn't allowed — this differs by phase).

CONTENT ACCURACY (non-negotiable):
- Never state a stat, player name, or number that is not present in the
  source content given to you. Do not fill gaps with plausible-sounding
  invented details.
- If given confirmed open bets, use ONLY those exact players/odds/bet types.
  Never alter, round, or reinterpret the odds or bet type.
- If given course/analysis content, do not imply a specific pick exists
  unless the source content explicitly states one.

OUTPUT FORMAT: Return a JSON array of strings, one string per tweet. Nothing else,
no markdown fences, no preamble.
"""


def generate_tweets():
    phase = "picks" if is_picks_phase() else "early_week"

    if phase == "picks":
        context = build_picks_phase_context()
        instruction = (
            f"Write {TWEETS_PER_RUN} tweets about {TOURNAMENT['name']} {TOURNAMENT['year']} "
            f"picks, using ONLY the confirmed open bets below. Vary angle across tweets "
            f"(one could highlight a value screen edge, one a tier/category summary). "
            f"Use hashtag {TOURNAMENT['hashtag']} in at least one.\n\n"
            f"LINK REQUIRED: this content always routes to Brian for manual posting, so "
            f"include {PICKS_URL} and \"{DISCLAIMER}\" in at least one tweet if not all.\n\n{context}"
        )
    else:
        context = build_early_week_context()
        instruction = (
            f"Write {TWEETS_PER_RUN} tweets about {TOURNAMENT['name']} {TOURNAMENT['year']}, "
            f"covering course profile, model methodology angle, or a stat that matters this week. "
            f"Do NOT mention any specific player pick, odds, or bet — this is early-week content only, "
            f"picks are not live yet. Use hashtag {TOURNAMENT['hashtag']} in at least one.\n\n"
            f"LINK FORBIDDEN: this content auto-posts without human review. Do NOT include "
            f"{PICKS_URL}, strokesedge.com, or any URL/link in ANY tweet — no exceptions, even "
            f"if character count would allow it. The disclaimer text alone (no link) is fine to "
            f"include if space allows, but is not required.\n\n{context}"
        )

    raw = call_claude(SYSTEM_PROMPT, instruction)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.M).strip()

    try:
        tweets = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(f"Model did not return valid JSON:\n{raw}")

    return phase, tweets


TWITTER_CHAR_LIMIT = 280


def needs_review(tweet_text, phase):
    """Second safety net: even in early_week phase, flag anything that smells like a pick,
    contains the site link, or exceeds X's actual post length limit.

    The over-length check exists because the system prompt's "hard limit: 280
    characters" is a request, not an enforced constraint — confirmed live
    2026-07-30: a real generated early-week tweet came back at 299 characters
    despite the instruction. Previously this was left as something to
    "spot-check... before approving" per the README, which only worked because
    a human looked at every tweet before it posted. Now that link-free content
    can auto-post with nobody reading it first, an over-length tweet needs to
    stop and get reviewed rather than get retried forever by post_tweets.py
    against the X API (which would reject it every single time, the same
    tweet, indefinitely) or fail some other way.
    """
    if phase == "picks":
        return True  # ALL picks-phase content requires human review, no exceptions
    if contains_site_link(tweet_text):
        return True
    if len(tweet_text) > TWITTER_CHAR_LIMIT:
        return True
    lowered = tweet_text.lower()
    return any(trigger.lower() in lowered for trigger in REVIEW_TRIGGER_WORDS)


if __name__ == "__main__":
    phase, tweets = generate_tweets()
    print(f"Phase: {phase}")
    for t in tweets:
        flag = "REVIEW REQUIRED" if needs_review(t, phase) else "auto-approved"
        print(f"\n[{flag}] ({len(t)} chars)\n{t}")
