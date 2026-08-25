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
    "name": "TOUR Championship",
    "year": 2026,
    "course_file": "course-east-lake.html",
    "analysis_file": "analysis.html",
    "methodology_file": "methodology.html",
    "hashtag": "#TOURChampionship",
}

# site pages live under "Strokes Edge Website HTML/" inside the repo, not
# the repo root directly (see legacy_v1/config.py note — this bit us once
# already: pointing at the repo root makes load_local_file() silently
# return None for every file).
SITE_REPO = r"C:\Users\bkopp\strokesedge-site\Strokes Edge Website HTML"

# Structured course facts and model weights, transcribed directly from the
# live site pages (course-east-lake.html, analysis.html) as of 2026-08-25
# — exists so chart_gen.py can plot them without scraping/parsing HTML text
# at chart-generation time. Edit alongside TOURNAMENT each week; never add
# a number that isn't actually published on the site pages (same content-
# accuracy rule as everywhere else in this pipeline). Fields with no
# verified on-page source (e.g. field size beyond "30-player, no cut" —
# fairway acreage isn't published for East Lake) are simply omitted, not
# guessed.
COURSE_STATS = {
    "par": 70,                        # 2026, per pgatour.com course-stats — matches Wikipedia post-2023-24 restoration
    "yardage": 7440,
    "location": "Atlanta, Georgia",
    "designer": "Tom Bendelow (1908), Donald Ross (1913), Andrew Green (2023-24 restoration)",
    "notable_hole": "9th: 260-yard par 3, one of the longest on Tour",
}

# Top L1 model weights for the current tournament, transcribed from
# analysis.html's "Predictive Stats" section (its own published weighting,
# not a fixed/global model constant) — re-transcribe here whenever that
# section's numbers change week to week. Order matches the site (highest
# weight first); generate_methodology_chart() only plots the top 5.
MODEL_WEIGHTS = [
    ("SG: Approach", 17),
    ("SG: Off the Tee", 14),
    ("SG: Putting", 13),
    ("Course-Fit Approach Comp", 9),
    ("Driving Distance Fit", 8),
]
