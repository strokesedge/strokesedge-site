"""
Single source of truth for "does this text contain a link back to the
site." Both streams need this for opposite reasons — Stream 1 must never
post a link (hard safety net in stream1_auto/post_tweets.py), Stream 2
must always include one (every option is meant to drive traffic) — so the
definition of "contains a link" lives in exactly one place rather than two
copies that could quietly drift apart.
"""

LINK_MARKERS = ("strokesedge.com", "picks.html")


def contains_site_link(text):
    lowered = text.lower()
    return any(marker in lowered for marker in LINK_MARKERS)
