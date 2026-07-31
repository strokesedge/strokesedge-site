"""
StrokesEdge Twitter Auto-Poster — Tracker reader

Determines whether we are in "early week" (course/analysis content only)
or "picks phase" (confirmed bets exist in the tracker for this tournament)
by reading the Google Sheet CSV directly. This is the ONLY source ever
used for player names / odds in a public post — never analysis.html.
"""

import csv
import io
import sys
import urllib.request
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from config import TRACKER_CSV_URL, TOURNAMENT


def fetch_tracker_rows():
    """Downloads and parses the tracker CSV. Returns list of dict rows."""
    req = urllib.request.Request(
        TRACKER_CSV_URL,
        headers={"User-Agent": "Mozilla/5.0 (StrokesEdge internal tool)"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(raw))
    return list(reader)


def get_open_bets_for_tournament(tournament_name=None):
    """
    Returns tracker rows matching the current tournament where result == 'open'.
    Column names assumed per master instructions:
    player | tournament | date | type | odds | wager | payout | result
    """
    tournament_name = tournament_name or TOURNAMENT["name"]
    rows = fetch_tracker_rows()

    matches = []
    for row in rows:
        # tolerate slight naming/case variance in the sheet
        row_tourney = (row.get("tournament") or "").strip().lower()
        row_result = (row.get("result") or "").strip().lower()
        if tournament_name.lower() in row_tourney and row_result == "open":
            matches.append(row)
    return matches


def is_picks_phase():
    """
    True if the tracker has one or more OPEN bets logged for the current
    tournament. This is the single switch between early-week content
    (course/analysis, safe to auto-post) and picks-phase content
    (must route through human review, per REVIEW_TRIGGER_WORDS / config).
    """
    try:
        bets = get_open_bets_for_tournament()
        return len(bets) > 0
    except Exception as e:
        # Network failure or bad CSV — fail safe to "early week" mode
        # rather than risk fabricating pick content.
        print(f"[tracker] Could not reach tracker CSV, defaulting to early-week mode: {e}")
        return False


if __name__ == "__main__":
    phase = "PICKS PHASE" if is_picks_phase() else "EARLY WEEK"
    print(f"[{datetime.now().isoformat()}] Current phase: {phase}")
    if phase == "PICKS PHASE":
        for b in get_open_bets_for_tournament():
            print(b)
