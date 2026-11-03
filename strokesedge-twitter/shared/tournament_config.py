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
    "name": "World Wide Technology Championship",
    "year": 2026,
    "course_file": "course-el-cardonal.html",
    "analysis_file": "analysis-world-wide-technology-championship-2026.html",
    "methodology_file": "methodology.html",
    "hashtag": "#WWTChampionship",
}

# site pages live under "Strokes Edge Website HTML/" inside the repo, not
# the repo root directly (see legacy_v1/config.py note — this bit us once
# already: pointing at the repo root makes load_local_file() silently
# return None for every file).
SITE_REPO = r"C:\Users\bkopp\strokesedge-site\Strokes Edge Website HTML"

# Structured course facts, transcribed directly from the live site pages
# (course-el-cardonal.html, analysis.html) as of 2026-11-02 — exists so chart_gen.py can plot them
# without scraping/parsing HTML text at chart-generation time. Edit
# alongside TOURNAMENT each week; never add a number that isn't actually
# published on the site pages (same content-accuracy rule as everywhere
# else in this pipeline). fairway_acres/notable_hole omitted this week —
# not published as a specific number/hole on the course page, so left out
# rather than guessed (chart_gen.py treats both as optional).
COURSE_STATS = {
    "par": 72,
    "yardage": 7452,
    "location": "Cabo San Lucas, Mexico",
    "designer": "Tiger Woods",
}

# Full StrokesEdge model workbook ran for this event (real Data Golf
# field/odds, not a directional estimate — see weekly-model/world-wide-
# technology-championship/weights_proposal.md for the full weight table and backtest
# trail). Top 5 weights, transcribed from analysis.html's "What Stats
# Matter This Week" section as published, matching the live site exactly.
MODEL_WEIGHTS = [
    ("SG: Approach", 20),
    ("SG: Off the Tee", 14),
    ("Course-Fit Approach Component", 10),
    ("Driving Distance Fit", 10),
    ("SG: Around the Green", 10),
]
