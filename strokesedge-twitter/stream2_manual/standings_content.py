"""
Stream 2 — source-content assembly for the hourly picks-vs-live-standings
update. Separate from content.py (the 90-minute category rotation)
because this pulls from a different, additional source (shared/
leaderboard.py's Data Golf live feed) on its own gate and cadence.

Parlay bets are deliberately excluded here — a parlay's settlement depends
on multiple legs together, and this feature only ever reports one
player's live position, never a compound win/loss judgment. Single-player
open bets only.
"""

import os
import sys

_SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

from tournament_config import TOURNAMENT
from tracker import get_open_bets_for_tournament
from leaderboard import get_live_leaderboard, match_player


def build_standings_matchups():
    """Returns a list of {player, position, score_to_par, round, thru,
    today, bets: [{type, odds}, ...]} — one entry per player with at least
    one open single-player bet AND a live leaderboard match. Returns None
    if there's no live leaderboard data this run, or no open single-player
    bet matched a live row (name mismatch, player not in field, etc.) —
    callers must fall back to skipping the slot, never guess a position."""
    bets = get_open_bets_for_tournament()
    if not bets:
        return None

    leaderboard = get_live_leaderboard()
    if not leaderboard:
        return None

    by_player = {}
    for b in bets:
        raw_player = (b.get("player") or "").strip()
        if not raw_player or "/" in raw_player or "parlay" in raw_player.lower():
            continue  # parlay leg list — excluded, see module docstring
        row = match_player(raw_player, leaderboard)
        if not row:
            continue
        entry = by_player.setdefault(raw_player, {
            "player": raw_player,
            "position": row["position"],
            "score_to_par": row["score_to_par"],
            "round": row["round"],
            "thru": row["thru"],
            "today": row["today"],
            "bets": [],
        })
        entry["bets"].append({"type": b.get("type", "?"), "odds": b.get("odds", "?")})

    return list(by_player.values()) or None


def build_standings_context():
    """Returns the source-content string for the Claude prompt, or None if
    there's nothing usable right now."""
    matchups = build_standings_matchups()
    if not matchups:
        return None

    lines = [
        f"LIVE STANDINGS for open {TOURNAMENT['name']} {TOURNAMENT['year']} picks, "
        f"cross-referenced from Data Golf's live feed against the tracker CSV's open bets. "
        f"Use ONLY these exact values below — never alter, round, or invent a position, "
        f"score, or hole count, and never state or imply a bet has won/lost/pushed since "
        f"these are IN-PROGRESS positions, not final results:"
    ]
    for m in matchups:
        bet_desc = "; ".join(f"{b['type']} ({b['odds']})" for b in m["bets"])
        score = m["score_to_par"]
        score_str = f"{score:+d}" if isinstance(score, int) else str(score)
        if m.get("thru"):
            progress = f"thru {m['thru']} in round {m.get('round')}"
        else:
            progress = f"round {m.get('round')} not yet teed off" if m.get("round") else "round in progress"
        lines.append(f"- {m['player']} ({bet_desc}): currently {m['position']}, {score_str}, {progress}")

    return "\n".join(lines)
