"""
Sportsbook win odds for the current tournament, for Stream 1's "odds"
category. Source: Data Golf's betting-tools/outrights feed (same
DATAGOLF_API_KEY the rest of the pipeline uses), read for ONE sportsbook so
every price in a tweet can be attributed to a named book.

This is market data only. It never touches the model's rankings, edges or
the unpublished picks card, so an odds tweet cannot reveal or imply a
StrokesEdge pick. Fails safe (returns None) on any request error, missing
key, event-name mismatch against shared/tournament_config.py, or a feed with
no price from the chosen book: a skipped slot is a missed tweet, a wrong
price in an unattended public tweet is not acceptable.
"""

import re

from tournament_config import TOURNAMENT
from leaderboard import _dg_get

BOOK_KEY = "draftkings"
BOOK_LABEL = "DraftKings"
TOP_N = 10


def _price_int(raw):
    m = re.fullmatch(r"\s*([+-]\d{2,6})\s*", str(raw or ""))
    return int(m.group(1)) if m else None


def _implied_pct(price):
    """Implied win probability from an American price, one decimal."""
    if price > 0:
        return round(100.0 / (price + 100.0) * 100.0, 1)
    return round(abs(price) / (abs(price) + 100.0) * 100.0, 1)


def _display_name(dg_name):
    if "," in dg_name:
        last, first = [p.strip() for p in dg_name.split(",", 1)]
        return f"{first} {last}"
    return dg_name


def get_market_odds():
    """Returns {'event', 'updated', 'rows': [{name, price, price_str, implied}]}
    sorted shortest price first, or None if nothing safe to say right now."""
    try:
        payload = _dg_get("betting-tools/outrights",
                          {"tour": "pga", "market": "win", "odds_format": "american"})
    except Exception as e:
        print(f"[market_odds] Could not reach Data Golf outrights feed: {e}")
        return None

    feed_event = (payload.get("event_name") or "").strip().lower()
    configured = TOURNAMENT["name"].strip().lower()
    if not feed_event or (feed_event not in configured and configured not in feed_event):
        print(f"[market_odds] Feed event {payload.get('event_name')!r} does not match "
              f"configured tournament {TOURNAMENT['name']!r}, skipping.")
        return None

    rows = []
    for r in payload.get("odds") or []:
        price = _price_int(r.get(BOOK_KEY))
        name = r.get("player_name")
        if price is None or not name:
            continue
        rows.append({
            "name": _display_name(name),
            "price": price,
            "price_str": f"{price:+d}",
            "implied": _implied_pct(price),
        })
    if len(rows) < TOP_N:
        return None
    rows.sort(key=lambda x: x["price"])
    return {"event": payload.get("event_name"), "updated": payload.get("last_updated"), "rows": rows}


def player_display_names():
    data = get_market_odds()
    return [r["name"] for r in data["rows"]] if data else []


def build_odds_context():
    data = get_market_odds()
    if not data:
        return None
    rows = data["rows"]
    top = rows[:TOP_N]
    lines = [
        f"WIN ODDS at {BOOK_LABEL} for the {TOURNAMENT['name']} {TOURNAMENT['year']} "
        f"(Data Golf betting feed, last updated {data['updated']}). Use ONLY these exact figures. "
        f"Never alter, round or invent a price or a name. These are sportsbook prices, not predictions.",
        "",
        f"SHORTEST PRICES ({BOOK_LABEL}, American odds, implied win probability):",
    ]
    for i, r in enumerate(top, 1):
        lines.append(f"- {i}. {r['name']}: {r['price_str']} (implied {r['implied']}%)")
    fav = rows[0]
    n_3000 = sum(1 for r in rows if r["price"] <= 3000)
    n_10000 = sum(1 for r in rows if r["price"] >= 10000)
    lines += [
        "",
        "DERIVED FACTS (already computed, use these instead of doing your own arithmetic):",
        f"- Favorite: {fav['name']} at {fav['price_str']}",
        f"- Players priced {BOOK_LABEL} at +3000 or shorter: {n_3000}",
        f"- Players priced at +10000 or longer: {n_10000}",
        f"- Players with a {BOOK_LABEL} price: {len(rows)}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(build_odds_context())
