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
    "name": "FedEx St. Jude Championship",
    "year": 2026,
    "course_file": "course-tpc-southwind.html",
    "analysis_file": "analysis.html",
    "methodology_file": "methodology.html",
    "hashtag": "#FedExStJude",
}

# site pages live under "Strokes Edge Website HTML/" inside the repo, not
# the repo root directly (see legacy_v1/config.py note — this bit us once
# already: pointing at the repo root makes load_local_file() silently
# return None for every file).
SITE_REPO = r"C:\Users\bkopp\strokesedge-site\Strokes Edge Website HTML"

# Structured course facts and model weights, transcribed directly from the
# live site pages (course-tpc-southwind.html, analysis.html) as of
# 2026-08-11 — exists so chart_gen.py can plot them without scraping/
# parsing HTML text at chart-generation time. Edit alongside TOURNAMENT
# each week; never add a number that isn't actually published on the site
# pages (same content-accuracy rule as everywhere else in this pipeline).
# Fields with no verified on-page source (e.g. field size — not stated
# anywhere on the current pages) are simply omitted, not guessed. No
# fairway-acreage figure is published for Southwind, so that key is
# omitted rather than carried over from last week's course.
COURSE_STATS = {
    "par": 70,                        # 2026 post-renovation; Wikipedia's stale pre-reno par/yardage don't apply
    "yardage": 7288,
    "location": "Memphis, Tennessee",
    "designer": "Ron Prichard (1988), with Hubert Green and Fuzzy Zoeller consulting",
    "notable_hole": "11th: island green, par 3, modeled on TPC Sawgrass's 17th",
}

# Top L1 model weights for the current tournament, transcribed from
# analysis.html's "What Stats Matter This Week" section (its own published
# weighting, not a fixed/global model constant) — re-transcribe here
# whenever that section's numbers change week to week.
#
# Left empty this week: as of 2026-08-11 analysis.html explicitly states
# the numeric model workbook for the FedEx St. Jude Championship hasn't
# published yet ("not final numeric model weights... full numeric weights
# ... in the StrokesEdge Substack workbook once published") — only a
# qualitative ranking (SG: Approach #1, Driving Accuracy overweighted by
# the market, Course History/Experience discounted for the 2025 reno) is
# live. Per chart_gen.should_chart(), an empty list here correctly skips
# the methodology chart and falls back to text-only rather than posting
# fabricated percentages. Fill in real numbers here the moment the
# workbook publishes — do not guess in the meantime.
MODEL_WEIGHTS = []
