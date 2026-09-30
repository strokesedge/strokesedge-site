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
    "name": "Bank of Utah Championship",
    "year": 2026,
    "course_file": "course-black-desert-resort.html",
    "analysis_file": "analysis.html",
    "methodology_file": "methodology.html",
    "hashtag": "#BankOfUtahChampionship",
}

# site pages live under "Strokes Edge Website HTML/" inside the repo, not
# the repo root directly (see legacy_v1/config.py note — this bit us once
# already: pointing at the repo root makes load_local_file() silently
# return None for every file).
SITE_REPO = r"C:\Users\bkopp\strokesedge-site\Strokes Edge Website HTML"

# Structured course facts, transcribed directly from the live site pages
# (course-black-desert-resort.html, analysis-bank-of-utah-championship-
# 2026.html) as of 2026-09-30 — exists so chart_gen.py can plot them
# without scraping/parsing HTML text at chart-generation time. Edit
# alongside TOURNAMENT each week; never add a number that isn't actually
# published on the site pages (same content-accuracy rule as everywhere
# else in this pipeline). fairway_acres/notable_hole omitted this week —
# not published as a specific number/hole on the course page, so left out
# rather than guessed (chart_gen.py treats both as optional).
COURSE_STATS = {
    "par": 71,                        # cross-checked pgatour.com + official tournament record, confirmed on course-black-desert-resort.html
    "yardage": 7421,
    "location": "Ivins, Utah",
    "designer": "Tom Weiskopf and Phil Smith (2023)",
}

# Full StrokesEdge model workbook ran for this event (real Data Golf
# field/odds, not a directional estimate — see weekly-model/bank-of-utah-
# championship/weights_proposal.md for the full weight table and backtest
# trail). Top 5 weights, transcribed from analysis.html's "What Stats
# Matter This Week" section as published, matching the live site exactly.
MODEL_WEIGHTS = [
    ("SG: Approach", 21),
    ("SG: Off the Tee", 16),
    ("SG: Putting", 14),
    ("Driving Distance Fit", 8),
    ("Course-Fit Approach Comp", 8),
]
