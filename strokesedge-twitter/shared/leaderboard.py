"""
Live PGA Tour leaderboard — Data Golf's in-play feed (same DATAGOLF_API_KEY
already used by ../../weekly-model). Used only by Stream 2's hourly
picks-vs-standings updates; nothing else in this project touches this
endpoint.

Fails safe (returns None) on any request error, missing key, or an
event-name mismatch against shared/tournament_config.py — a skipped update
is a missed email, a wrong-event update is a false public claim about live
positions, so only one of those is acceptable to risk unattended.
"""

import json
import os
import urllib.parse
import urllib.request

from tournament_config import TOURNAMENT

DATAGOLF_BASE = "https://feeds.datagolf.com"


def _dg_get(path, params):
    api_key = os.environ.get("DATAGOLF_API_KEY")
    if not api_key:
        raise RuntimeError("DATAGOLF_API_KEY environment variable is not set")
    query = dict(params)
    query["key"] = api_key
    query["file_format"] = "json"
    url = f"{DATAGOLF_BASE}/{path}?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "StrokesEdge internal tool"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_live_leaderboard(tour="pga"):
    """Returns a list of {player_name, position, score_to_par, round, thru,
    today} dicts for the tournament currently live on Data Golf's feed, or
    None if that feed's event doesn't match shared/tournament_config.py
    (e.g. it hasn't rolled over to this week's event yet) or the request
    fails outright. player_name is Data Golf's "Last, First" format —
    use match_player() below to line it up against tracker CSV names.
    """
    try:
        payload = _dg_get("preds/in-play", {"tour": tour})
    except Exception as e:
        print(f"[leaderboard] Could not reach Data Golf in-play feed: {e}")
        return None

    info = payload.get("info", {})
    feed_event = (info.get("event_name") or "").strip().lower()
    configured_event = TOURNAMENT["name"].strip().lower()
    if not feed_event or (feed_event not in configured_event and configured_event not in feed_event):
        print(f"[leaderboard] Live feed event {info.get('event_name')!r} does not match "
              f"configured tournament {TOURNAMENT['name']!r} — skipping rather than risk "
              f"a wrong-event post.")
        return None

    out = []
    for row in payload.get("data", []):
        out.append({
            "player_name": row.get("player_name"),
            "position": row.get("current_pos"),
            "score_to_par": row.get("current_score"),
            "round": row.get("round"),
            "thru": row.get("thru"),
            "today": row.get("today"),
        })
    return out


def _normalize_name(name):
    """Data Golf format: 'Last, First'. Tracker CSV format: 'First Last'.
    Normalizes both to a sorted lowercase token set so punctuation and
    ordering differences don't break the match."""
    return " ".join(sorted(name.replace(",", " ").lower().split()))


def match_player(player_name, leaderboard):
    """Finds player_name (tracker CSV format) in the live leaderboard.
    Returns the matching row dict, or None if not found — callers must
    treat 'not found' as 'no live data for this player this run', never
    guess a position."""
    target = _normalize_name(player_name)
    for row in leaderboard:
        if row.get("player_name") and _normalize_name(row["player_name"]) == target:
            return row
    return None
