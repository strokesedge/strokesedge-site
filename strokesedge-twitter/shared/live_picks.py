"""
Live commentary source: StrokesEdge's PUBLISHED picks for this week's
tournament (parsed from weekly-model/<slug>/substack_article_*.md, the free
public picks article) compared against Data Golf's live in-play leaderboard.

Why this exists separately from shared/tracker.py: the tracker CSV holds
Brian's actual placed bets, which are not always the published picks (see
the strokesedge-picks-vs-tracker memory note). Live commentary on "our
picks" is about the published card, so it is sourced from the article, not
the tracker. Odds are deliberately never carried into the context string,
so a tweet built from it cannot cite a price.

Fails safe everywhere: any problem (no article, event-name mismatch, feed
down, tournament not started, tournament finished) returns None and the
caller skips the slot. A skipped slot is a missed tweet; a wrong live claim
is a public factual error.
"""

import json
import os
import re

from tournament_config import TOURNAMENT
from leaderboard import get_live_feed

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEEKLY_MODEL_DIR = os.path.join(REPO_ROOT, "weekly-model")

TIER_LABELS = {
    "E/W WINNER": "outright pick",
    "LONGSHOT / VALUE": "longshot pick",
    "TOP 10 / TOP 20": "top-finish pick",
    "FADE": "faded outright (still viable for a top finish)",
}


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load_published_picks():
    """[{tier, tier_label, dg_name}] from this tournament's picks article,
    or None if the article is missing or is for a different event."""
    folder = os.path.join(WEEKLY_MODEL_DIR, _slug(TOURNAMENT["name"]))
    if not os.path.isdir(folder):
        return None
    candidates = sorted(f for f in os.listdir(folder) if f.startswith("substack_article_") and f.endswith(".md"))
    if not candidates:
        return None
    with open(os.path.join(folder, candidates[-1]), "r", encoding="utf-8") as f:
        text = f.read()
    if TOURNAMENT["name"].lower() not in text[:2000].lower():
        return None

    m = re.search(r"## 04 .*?Full Picks Card(.*?)(?=\n## 05)", text, re.S)
    if not m:
        return None
    picks, tier = [], None
    for line in m.group(1).splitlines():
        line = line.strip()
        header = re.match(r"^\*\*([A-Z0-9 /]+)\*\*$", line)
        if header:
            tier = header.group(1).strip()
            continue
        if tier in TIER_LABELS:
            entry = re.match(r"^- ([^()]+?) \(\s*[+-]?\d+\s*\)", line)
            if entry:
                picks.append({"tier": tier, "tier_label": TIER_LABELS[tier], "dg_name": entry.group(1).strip()})
    return picks or None


def _norm(name):
    return " ".join(sorted(name.replace(",", " ").lower().split()))


def _display(dg_name):
    if "," in dg_name:
        last, first = [p.strip() for p in dg_name.split(",", 1)]
        return f"{first} {last}"
    return dg_name


def _fmt_score(score):
    if isinstance(score, (int, float)):
        score = int(score)
        return "E" if score == 0 else f"{score:+d}"
    return str(score)


def _is_complete(rows):
    active = [r for r in rows if str(r.get("position")).upper() not in ("CUT", "WD", "DQ", "MDF")]
    return bool(active) and all((r.get("round") == 4 and r.get("thru") in (18, "F")) for r in active)


def _has_started(rows):
    return any((r.get("thru") not in (0, None)) or ((r.get("round") or 0) > 1) for r in rows)


def get_live_picks_status():
    """Returns {'info': ..., 'leaders': [...], 'picks': [...]} for picks that
    have a live row, or None if there is nothing safe to say right now."""
    published = load_published_picks()
    if not published:
        return None
    feed = get_live_feed()
    if not feed:
        return None
    info, rows = feed
    if not rows or not _has_started(rows) or _is_complete(rows):
        return None

    by_name = {_norm(r["player_name"]): r for r in rows if r.get("player_name")}
    picks = []
    for p in published:
        row = by_name.get(_norm(p["dg_name"]))
        if row:
            picks.append({**p, "row": row})
    if not picks:
        return None

    live = [r for r in rows if str(r.get("position")).upper() not in ("CUT", "WD", "DQ", "MDF")
            and isinstance(r.get("score_to_par"), (int, float))]
    leaders = sorted(live, key=lambda r: r["score_to_par"])[:5]
    return {"info": info, "leaders": leaders, "picks": picks}


def build_live_picks_context():
    status = get_live_picks_status()
    if not status:
        return None
    info = status["info"]
    lines = [
        f"LIVE STATUS for {TOURNAMENT['name']} {TOURNAMENT['year']} (Data Golf in-play feed, "
        f"current round {info.get('current_round')}, last update {info.get('last_update')}). "
        f"Use ONLY the exact values below. Never alter, round or invent a position, score or "
        f"hole count. These are IN-PROGRESS positions, never final results.",
        "",
        "CURRENT LEADERS:",
    ]
    for r in status["leaders"]:
        lines.append(f"- {_display(r['player_name'])}: {r['position']}, {_fmt_score(r['score_to_par'])}, "
                     f"thru {r['thru']} in round {r['round']}")
    leader_score = status["leaders"][0]["score_to_par"] if status["leaders"] else None
    lines += ["", "STROKESEDGE PUBLISHED PICKS, CURRENT POSITIONS:"]
    inside_top10, cut_names = [], []
    for p in status["picks"]:
        r = p["row"]
        pos = str(r["position"])
        if pos.upper() == "CUT":
            status_txt = "missed the cut"
            cut_names.append(_display(p["dg_name"]))
        else:
            gap = ""
            if leader_score is not None and isinstance(r["score_to_par"], (int, float)):
                diff = int(r["score_to_par"]) - int(leader_score)
                gap = ", tied for the lead" if diff == 0 else f", {diff} shot{'s' if diff != 1 else ''} behind the leader"
            status_txt = f"{pos}, {_fmt_score(r['score_to_par'])}, thru {r['thru']} in round {r['round']}{gap}"
            num = re.sub(r"\D", "", pos)
            if num and int(num) <= 10:
                inside_top10.append(f"{_display(p['dg_name'])} ({pos})")
        lines.append(f"- {_display(p['dg_name'])} ({p['tier_label']}): {status_txt}")
    lines += ["", "DERIVED FACTS (already computed, use these instead of doing your own arithmetic or counting):",
              f"- Published picks in the field with live data: {len(status['picks'])}",
              "- Picks inside the top 10 right now: " + (", ".join(inside_top10) if inside_top10 else "none"),
              "- Picks that missed the cut: " + (", ".join(cut_names) if cut_names else "none")]
    return "\n".join(lines)


if __name__ == "__main__":
    print(json.dumps(load_published_picks(), indent=1)[:1500])
    print(build_live_picks_context())
