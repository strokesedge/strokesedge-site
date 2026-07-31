"""
Thin wrapper around the Claude API — no content/voice logic here, that
belongs to each stream's own generator.py. Both streams call this the same
way; sharing it just means the max_tokens/thinking-budget fix below only
has to exist once.
"""

import json
import os
import urllib.request

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5"


MAX_TOKENS_CEILING = 16000


def _request(system_prompt, user_prompt, max_tokens):
    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
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
        return json.loads(resp.read().decode("utf-8"))


def call_claude(system_prompt, user_prompt, max_tokens=4000):
    """Returns the concatenated text blocks from the response.

    max_tokens defaults to 4000, not the more obvious 1000 — confirmed live
    in the legacy prototype (2026-07-30) that this model's 'thinking' block
    draws from the SAME budget as visible output text, and a real-sized
    prompt (course guide + analysis.html, ~8000 chars) burned the whole
    1000-token budget on thinking alone, leaving zero for the actual tweet
    text and silently returning an empty string.

    How much of that budget 'thinking' actually uses varies run to run for
    the same prompt, not just with prompt size — confirmed live 2026-07-31,
    the stream2 methodology-category prompt hit max_tokens at 6000 four
    times in a row in one test run right after succeeding at 6000 on a
    different category. Rather than push every caller to keep guessing a
    bigger fixed number, retry ONCE here with the budget doubled (capped
    at MAX_TOKENS_CEILING) before giving up — this is the single place
    that fix needs to live.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set.")

    data = _request(system_prompt, user_prompt, max_tokens)

    if data.get("stop_reason") == "max_tokens" and max_tokens < MAX_TOKENS_CEILING:
        retry_tokens = min(max_tokens * 2, MAX_TOKENS_CEILING)
        data = _request(system_prompt, user_prompt, retry_tokens)

    if data.get("stop_reason") == "max_tokens":
        raise RuntimeError(
            "Claude call hit max_tokens twice in a row (including a doubled-budget retry) "
            "before finishing — likely all budget spent on 'thinking' with none left for "
            "output text. Not retrying again rather than risk an unbounded retry loop."
        )

    text_parts = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
    return "\n".join(text_parts)
