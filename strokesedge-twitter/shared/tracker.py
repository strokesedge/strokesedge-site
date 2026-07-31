"""
Tracker CSV reader — the ONLY source ever used for player names, odds, or
results in a public post. Never analysis.html once picks are live, per the
site's own content-accuracy rule (see ../../CLAUDE.md).

Shared because both streams need the same facts about the same tracker —
this is data access, not workflow. Neither stream's routing/queue logic
lives here.

CSV columns: player | tournament | date | type | odds | wager | payout | result
Result values (lowercase only): open, won, lost, placed
"""

import csv
import io
import urllib.request

from tournament_config import TOURNAMENT

TRACKER_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRn7eBjHWBs4nag5K5QHxnKiyeC-UEobNINAfjmEKsnBgX6aqm3lEZCY1i4lg5t5Lwy3I2p8ZLrR4Gc/pub?gid=0&single=true&output=csv"


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


def _rows_for_tournament(tournament_name=None):
    tournament_name = tournament_name or TOURNAMENT["name"]
    rows = fetch_tracker_rows()
    return [
        row for row in rows
        if tournament_name.lower() in (row.get("tournament") or "").strip().lower()
    ]


def get_open_bets_for_tournament(tournament_name=None):
    """Rows for this tournament where result == 'open' — the only valid
    source for a live pick/odds mention (Stream 2's picks category)."""
    return [r for r in _rows_for_tournament(tournament_name)
            if (r.get("result") or "").strip().lower() == "open"]


def get_settled_bets_for_tournament(tournament_name=None):
    """Rows for this tournament where result is NOT 'open' — the only
    valid source for a post-tournament recap (Stream 1's recap category)."""
    return [r for r in _rows_for_tournament(tournament_name)
            if (r.get("result") or "").strip().lower() != "open"]


def is_picks_phase(tournament_name=None):
    """True if the tracker has one or more OPEN bets logged for the
    tournament — the switch between early-week content and picks-phase
    content. Fails safe to False (early-week / no picks content) on any
    fetch error rather than risk fabricating pick content."""
    try:
        return len(get_open_bets_for_tournament(tournament_name)) > 0
    except Exception as e:
        print(f"[tracker] Could not reach tracker CSV, defaulting to no-picks-phase: {e}")
        return False


def is_tournament_complete(tournament_name=None):
    """True only if the tracker has bets logged for this tournament AND
    none of them are still 'open'. Fails safe to False (no recap) on any
    fetch error or if there's simply no data yet — a recap that never
    fires is a missed tweet slot; a recap that fires early and guesses at
    an in-progress record is a false public claim. Only one of those is
    acceptable to risk automatically."""
    try:
        rows = _rows_for_tournament(tournament_name)
        if not rows:
            return False
        return not any((r.get("result") or "").strip().lower() == "open" for r in rows)
    except Exception as e:
        print(f"[tracker] Could not reach tracker CSV, defaulting to tournament-not-complete: {e}")
        return False


def summarize_final_results(rows):
    """Deterministic record tally, grouped by bet type — computed in code,
    not left to the model to add up, so a recap tweet's "3-for-8" can never
    be an LLM arithmetic mistake. 'cashed' = won + placed (both returned
    money); 'total' = every settled row regardless of outcome.

    Returns {"_overall": {...}, "<type>": {...}, ...} where each entry has
    won/placed/lost/cashed/total counts.
    """

    def blank():
        return {"won": 0, "placed": 0, "lost": 0}

    by_type = {}
    overall = blank()

    for row in rows:
        result = (row.get("result") or "").strip().lower()
        bet_type = (row.get("type") or "unspecified").strip() or "unspecified"
        if result not in ("won", "placed", "lost"):
            continue  # ignore anything not a settled result (e.g. stray blank rows)

        by_type.setdefault(bet_type, blank())
        by_type[bet_type][result] += 1
        overall[result] += 1

    def finalize(counts):
        cashed = counts["won"] + counts["placed"]
        total = cashed + counts["lost"]
        return {**counts, "cashed": cashed, "total": total}

    out = {"_overall": finalize(overall)}
    for bet_type, counts in by_type.items():
        out[bet_type] = finalize(counts)
    return out


if __name__ == "__main__":
    print("Picks phase:", is_picks_phase())
    print("Tournament complete:", is_tournament_complete())
    if is_tournament_complete():
        settled = get_settled_bets_for_tournament()
        print("Settled bets:", settled)
        print("Summary:", summarize_final_results(settled))
