"""
The current live tournament — a fact about the world, not pipeline logic.
Both streams tweet about the same tournament in the same week, so this one
fact is shared to avoid the two streams drifting out of sync (e.g. Stream 1
still talking about last week's course while Stream 2 already moved on).
Everything else — cadence, categories, queues, delivery — stays fully
separate in each stream's own config.py.

Edit TOURNAMENT here each week. Nothing else in this file should need to
change.
"""

TOURNAMENT = {
    "name": "Rocket Classic",
    "year": 2026,
    "course_file": "course-detroit-golf-club.html",
    "analysis_file": "analysis.html",
    "methodology_file": "methodology.html",
    "hashtag": "#RocketClassic",
}

# site pages live under "Strokes Edge Website HTML/" inside the repo, not
# the repo root directly (see legacy_v1/config.py note — this bit us once
# already: pointing at the repo root makes load_local_file() silently
# return None for every file).
SITE_REPO = r"C:\Users\bkopp\strokesedge-site\Strokes Edge Website HTML"
