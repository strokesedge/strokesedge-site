#!/usr/bin/env python3
"""
weekly_course_update.py — StrokesEdge unattended weekly course-page generator.

Runs every Sunday at 5pm via Windows Task Scheduler. Finds next week's PGA
Tour event, gets the host course's details, drafts a course-analysis page
with the Claude API, and stages it for publication.

═══════════════════════════════════════════════════════════════════════════
IMPORTANT DESIGN DECISION — READ BEFORE RUNNING UNATTENDED
═══════════════════════════════════════════════════════════════════════════
This script does NOT auto-push to GitHub, even in normal (non---test) mode.
It scrapes, calls the Claude API, writes the files, and creates a LOCAL git
commit — then stops and emails you a summary. Nothing goes live until you
run:

    python weekly_course_update.py --push

That command does nothing except push whatever is already committed.

Why: the Claude call uses a small, fast model with no web-search/grounding
in a plain API call. The prompt asks it for specific things — historical
winner patterns, stat weightings — that are exactly what a model without
live data access is most likely to get subtly wrong. This site brands
itself as a quantitative model; publishing unreviewed AI-generated
"analysis" with specific-sounding numbers straight to a live betting site,
unattended, forever, is a real accuracy risk to anyone using it to make
betting decisions. Holding the push costs you thirty seconds a week reading
the email and running one command. If you've decided you want the push
fully automatic anyway, search this file for "AUTO_PUSH" — there's a single
switch, clearly marked, that removes this guard. Flip it deliberately, not
by accident.
═══════════════════════════════════════════════════════════════════════════

Data sources (all verified working against live sites while writing this,
not guessed):
  - Tournament schedule, course name, location, dates, purse:
    pgatour.com/schedule's embedded __NEXT_DATA__ JSON (a Next.js
    server-rendered payload — reliable, not JS-rendered-only, no bot
    blocking encountered). ESPN's schedule page returned an empty
    bot-challenge response (HTTP 202, 0 bytes) during testing and PGA
    Tour's own schedule already includes majors and co-sanctioned events
    (verified: The Open Championship and Genesis Scottish Open both
    appear in the "R" tour-code schedule feed) — so ESPN and European
    Tour scraping were dropped rather than shipped as untested/broken.
  - Par / yardage: NOT present anywhere in the PGA Tour JSON (checked
    every field on multiple tournaments). Falls back to Wikipedia's
    {{Infobox golf facility}} template (par1/length1 fields), resolved
    via Wikipedia's opensearch API so it doesn't depend on guessing the
    exact article title. This works for most tournament-host courses but
    not all — e.g. Bellerive Country Club has no infobox on Wikipedia at
    all. When it's missing, the field is marked "TBD" rather than
    invented, and this is logged.
  - Course type (links/parkland/desert/etc): no reliable structured
    source exists for this. Inferred with a simple keyword heuristic
    (see infer_course_type) — treat this as a rough guess, not a fact.

AUTO-CLASSIFICATION LIMITATION:
  The PGA Tour schedule JSON has no field for "is this a major" or "is
  this a team event" — those lists below (MAJORS, ELEVATED_EVENTS,
  SKIP_KEYWORDS) are hardcoded and need manual upkeep as the PGA Tour
  schedule/branding changes year to year (e.g. signature event names or
  sponsor names change). This is not something that can be reliably
  auto-detected from the data available.

Usage:
  python weekly_course_update.py            Normal unattended run: scrape,
                                             generate, write files, commit
                                             locally, email summary. Does
                                             NOT push (see above).
  python weekly_course_update.py --push     Push whatever is already
                                             locally committed. Does nothing
                                             else — no scraping, no API call.
  python weekly_course_update.py --test     Scrape + generate + print
                                             everything to the terminal.
                                             Writes no files, makes no git
                                             commit, sends no email.
"""

import argparse
import atexit
import json
import logging
import os
import re
import smtplib
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from email.mime.text import MIMEText
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent
SITE_DIR = REPO_ROOT / "Strokes Edge Website HTML"
TEMPLATE_FILE = SITE_DIR / "course-quail-hollow.html"
COURSES_INDEX_FILE = SITE_DIR / "courses.html"
SITEMAP_FILE = SITE_DIR / "sitemap.xml"
LOG_FILE = REPO_ROOT / "weekly_course_update.log"
LOCK_FILE = REPO_ROOT / ".weekly_course_update.lock"

# How old an unclaimed lock file has to be before we treat it as an orphan
# from a crashed run rather than a live instance. Normal runs (including
# --push) finish in well under a minute; 15 minutes is a generous margin
# that still clears the lock long before the next weekly trigger.
LOCK_STALE_SECONDS = 15 * 60

# Safety allowlist — the ONLY files this script is permitted to write.
# Enforced in write_text(); anything else is a bug, not a config option.
ALLOWED_WRITE_TARGETS = {COURSES_INDEX_FILE, SITEMAP_FILE}  # + the new course page, checked separately

# Set to True only if you have deliberately decided to skip the review
# step described in the module docstring above.
AUTO_PUSH = False

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ─────────────────────────────────────────────────────────────────────────
# Event classification — hardcoded, needs manual upkeep (see docstring)
# ─────────────────────────────────────────────────────────────────────────
MAJORS = {
    "masters tournament", "u.s. open", "us open", "the open championship",
    "pga championship",
}
ELEVATED_EVENTS = {
    "the sentry", "the american express", "farmers insurance open",
    "at&t pebble beach pro-am", "wm phoenix open", "arnold palmer invitational",
    "the players championship", "genesis invitational", "rbc heritage",
    "truist championship", "wells fargo championship", "the memorial tournament",
    "the travelers championship", "genesis scottish open",  # also co-sanctioned
    "bmw championship", "fedex st. jude championship", "tour championship",
}
CO_SANCTIONED_KEYWORDS = ("scottish open", "irish open", "isco championship")
SKIP_KEYWORDS = (
    "zurich classic", "qbe shootout", "liv golf", "korn ferry", "champions tour",
    "lpga", "presidents cup", "ryder cup",  # team/exhibition, not weekly stroke-play
)


def is_skippable(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in SKIP_KEYWORDS)


def priority_rank(name: str) -> int:
    """Lower = higher priority. Used to pick among same-week events."""
    n = name.lower()
    if n in MAJORS or any(m in n for m in MAJORS):
        return 0
    if n in ELEVATED_EVENTS or any(e in n for e in ELEVATED_EVENTS):
        return 1
    if any(kw in n for kw in CO_SANCTIONED_KEYWORDS):
        return 2
    return 3


# ─────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────
logger = logging.getLogger("weekly_course_update")
logger.setLevel(logging.INFO)
_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(_file_handler)

# Windows Task Scheduler runs this with whatever console codepage is
# configured system-wide, which is frequently NOT UTF-8 (cp1252/cp437
# are common defaults). Log messages use real em dashes and arrows.
# Rather than assume the console can render them (confirmed it can't,
# in at least one terminal, while testing this locally), make console
# output degrade to '?' instead of crashing the whole run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_console_handler)


# ─────────────────────────────────────────────────────────────────────────
# HTTP helper
# ─────────────────────────────────────────────────────────────────────────
def http_get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────
# STEP 1 — find next week's tournament (pgatour.com)
# ─────────────────────────────────────────────────────────────────────────
def fetch_pga_schedule() -> list:
    """Returns the raw list of tournament dicts from pgatour.com's schedule
    JSON, or raises RuntimeError if the page can't be fetched or parsed."""
    html = http_get("https://www.pgatour.com/schedule")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.S)
    if not m:
        raise RuntimeError("pgatour.com/schedule: __NEXT_DATA__ script tag not found — page structure may have changed")
    data = json.loads(m.group(1))
    try:
        queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
        schedule_q = next(q for q in queries if q["queryKey"][0] == "schedule")
        tournaments = schedule_q["state"]["data"]["tournaments"]
    except (KeyError, StopIteration) as e:
        raise RuntimeError(f"pgatour.com/schedule: expected JSON shape not found ({e}) — page structure may have changed")
    if not tournaments:
        raise RuntimeError("pgatour.com/schedule: tournaments list is empty")
    return tournaments


def pick_next_tournament(tournaments: list) -> dict:
    """Finds the next coverable tournament: the earliest upcoming week,
    preferring majors > elevated > co-sanctioned > standard among any
    events sharing that week, skipping team/LIV/other-tour events. If the
    earliest week has nothing coverable, moves to the next week."""
    upcoming = [t for t in tournaments if t.get("status") == "UPCOMING"]
    if not upcoming:
        raise RuntimeError("No UPCOMING tournaments found in schedule data")

    # Group by displayDate (a reasonable proxy for "same week" — PGA Tour's
    # own feed already dates same-week events identically in every case
    # observed while building this).
    weeks = {}
    for t in upcoming:
        weeks.setdefault(t.get("displayDate"), []).append(t)

    # Preserve chronological order as it appears in the source feed.
    seen_dates = []
    for t in upcoming:
        if t.get("displayDate") not in seen_dates:
            seen_dates.append(t.get("displayDate"))

    for display_date in seen_dates:
        candidates = [t for t in weeks[display_date] if not is_skippable(t.get("name", ""))]
        if not candidates:
            continue
        candidates.sort(key=lambda t: priority_rank(t.get("name", "")))
        return candidates[0]

    raise RuntimeError("Every upcoming tournament in the schedule matched a SKIP keyword — nothing coverable found")


# ─────────────────────────────────────────────────────────────────────────
# STEP 2 — course details (par/yardage fallback via Wikipedia)
# ─────────────────────────────────────────────────────────────────────────
def wikipedia_resolve_title(query: str) -> str | None:
    url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit=1&format=json"
    try:
        raw = http_get(url, timeout=10)
        result = json.loads(raw)
        titles = result[1]
        return titles[0] if titles else None
    except Exception as e:
        logger.info(f"Wikipedia title resolution failed for '{query}': {e}")
        return None


def wikipedia_par_yardage(course_name: str) -> tuple:
    """Returns (par, yardage) as strings, or (None, None) if unavailable.
    Never raises — this is a best-effort fallback, not a required source."""
    title = wikipedia_resolve_title(course_name)
    if not title:
        return None, None
    try:
        url = (f"https://en.wikipedia.org/w/api.php?action=parse&page="
               f"{urllib.parse.quote(title)}&prop=wikitext&format=json")
        raw = http_get(url, timeout=10)
        data = json.loads(raw)
        wikitext = data["parse"]["wikitext"]["*"]
    except Exception as e:
        logger.info(f"Wikipedia wikitext fetch failed for '{title}': {e}")
        return None, None

    infobox = re.search(r"\{\{Infobox golf[^\n]*\n(.*?)\n\}\}", wikitext, re.S | re.I)
    if not infobox:
        logger.info(f"Wikipedia page '{title}' has no golf infobox — par/yardage unavailable")
        return None, None
    body = infobox.group(1)

    par_m = re.search(r"\bpar1?\s*=\s*([0-9/]+)", body, re.I)
    len_m = re.search(r"\blength1?\s*=\s*\{\{convert\|([0-9,]+)\|yd", body, re.I)

    par = par_m.group(1).split("/")[0] if par_m else None
    yards = len_m.group(1).replace(",", "") if len_m else None
    yards = f"{int(yards):,}" if yards else None
    return par, yards


def infer_course_type(course_name: str, location: str) -> str:
    """Rough heuristic only — no reliable structured source for this
    exists. Verify manually for any course this looks wrong on."""
    text = f"{course_name} {location}".lower()
    if any(k in text for k in ("scotland", "ireland", "england", "wales", "st andrews", "links")):
        return "links"
    if any(k in text for k in ("arizona", "nevada", "scottsdale", "palm springs", "desert")):
        return "desert"
    if any(k in text for k in ("florida", "hawaii", "bahamas", "caribbean")):
        return "coastal/tropical parkland"
    return "parkland"


def get_course_details(tournament: dict) -> dict:
    course_data = tournament.get("courseData") or {}
    course_name = course_data.get("name")
    if not course_name:
        raise RuntimeError(f"Tournament '{tournament.get('name')}' has no courseData.name in schedule feed")

    city = course_data.get("city", "")
    state = course_data.get("stateCode", "")
    country = course_data.get("country", "")
    location = ", ".join(p for p in [city, state or country] if p)

    par, yardage = wikipedia_par_yardage(course_name)
    if not par or not yardage:
        logger.info(f"Par/yardage missing for '{course_name}' after Wikipedia fallback — marking TBD")
    par = par or "TBD"
    yardage = yardage or "TBD"

    return {
        "course_name": course_name,
        "tournament_name": tournament["name"],
        "location": location or "TBD",
        "par": par,
        "yardage": yardage,
        "dates": tournament.get("displayDate", "TBD"),
        "purse": tournament.get("purse", ""),
        "course_type": infer_course_type(course_name, location),
    }


# ─────────────────────────────────────────────────────────────────────────
# STEP 3 — Claude API course analysis
# ─────────────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_MAX_TOKENS = 2000

ANALYSIS_PROMPT_TEMPLATE = """You are StrokesEdge, a quantitative PGA Tour golf betting analytics brand. Write a detailed course profile for {course_name} hosting {tournament_name} ({dates}, {location}).

Cover all of the following sections:
- Course overview: layout type, yardage, par, course design philosophy, what makes it unique
- Primary defense: what the course uses to separate the field (rough, wind, greens, length, accuracy)
- What stats matter most: rank the SG categories (OTT, APP, ARG, PUTT) with specific weightings and explain why each matters or doesn't at this course
- Historical winner profile: what type of player wins here, any patterns in past winners
- Key betting angles: what the model looks for, which player types have an edge, what to fade
- Course conditions: typical weather, green speed, firmness

Rules:
- Data-forward, analytical tone
- No em dashes in prose body text
- No bullet-heavy formatting
- No tidy summary sentences
- Vary sentence rhythm
- Around 600-800 words total"""


def generate_analysis(details: dict) -> str | None:
    """Calls the Claude API. Returns the generated text, or None if the
    call fails for any reason — caller decides whether that's fatal."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable is not set")
        return None

    prompt = ANALYSIS_PROMPT_TEMPLATE.format(**details)
    body = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": CLAUDE_MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return "".join(block.get("text", "") for block in result.get("content", []))
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        return None


def split_analysis_into_sections(analysis_text: str) -> dict:
    """The prompt asks for 6 labeled sections but Claude's exact heading
    style will vary. Splits on lines that look like section headers
    (short line, title case or ending in a colon) rather than assuming
    an exact format, and falls back to putting everything in one section
    if splitting doesn't find clean boundaries."""
    labels = [
        "Course overview", "Primary defense", "What stats matter",
        "Historical winner", "Key betting angles", "Course conditions",
    ]
    pattern = re.compile(
        r"^\s*(?:#+\s*)?(" + "|".join(re.escape(l) for l in labels) + r")[^\n]*[:\n]",
        re.I | re.M,
    )
    matches = list(pattern.finditer(analysis_text))
    if len(matches) < 3:
        # Splitting didn't find enough of the expected headers — safer to
        # keep the whole thing as one block than to silently mis-split it.
        return {"full": analysis_text.strip()}

    sections = {}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(analysis_text)
        key = m.group(1).lower().split()[0]
        sections[key] = analysis_text[start:end].strip()
    return sections


# ─────────────────────────────────────────────────────────────────────────
# File I/O helpers (BOM-preserving, like the rest of this repo's tooling)
# ─────────────────────────────────────────────────────────────────────────
def read_text(path: Path) -> tuple:
    """Returns (text, has_bom, had_crlf). Every file in this repo uses
    CRLF line endings; reading raw bytes + decode() (needed to control
    BOM handling precisely) does NOT do Python's usual universal-newline
    translation, so the text this returns contains literal '\\r\\n'
    unless we normalize it ourselves. Every marker string in this file is
    written assuming plain '\\n' — without this normalization, every
    multi-line text.find()/text.replace() against real repo files
    silently fails to match. (Found by running --test against the real
    files, not by inspection — the sitemap.xml update raised exactly this
    way on the first real run.)"""
    raw = path.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig" if has_bom else "utf-8")
    had_crlf = "\r\n" in text
    if had_crlf:
        text = text.replace("\r\n", "\n")
    return text, has_bom, had_crlf


def write_text(path: Path, text: str, has_bom: bool, had_crlf: bool) -> None:
    resolved = path.resolve()
    allowed = {p.resolve() for p in ALLOWED_WRITE_TARGETS}
    is_new_course_page = (
        resolved.parent == SITE_DIR.resolve()
        and resolved.name.startswith("course-")
        and resolved.name.endswith(".html")
    )
    if resolved not in allowed and not is_new_course_page:
        raise RuntimeError(f"Refusing to write outside the allowed target set: {path}")
    if had_crlf:
        text = text.replace("\n", "\r\n")
    data = text.encode("utf-8")
    if has_bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def slugify(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


# ─────────────────────────────────────────────────────────────────────────
# STEP 4 — build the course page
# ─────────────────────────────────────────────────────────────────────────
def build_course_page(details: dict, analysis_text: str, analysis_failed: bool) -> tuple:
    template, has_bom, had_crlf = read_text(TEMPLATE_FILE)
    slug = details["slug"]
    course = details["course_name"]
    tourn = details["tournament_name"]
    location = details["location"]
    par = details["par"]
    yardage = details["yardage"]

    # Avoid "for the The Open Championship" when a tournament name already
    # starts with "The" (found by running --test against a real upcoming
    # major, not a hypothetical edge case).
    tourn_with_article = tourn if tourn.lower().startswith("the ") else f"the {tourn}"

    title_tag = f"{course} Betting Guide — {tourn} Course Profile | StrokesEdge"
    meta_desc = (f"The complete {course} betting guide for {tourn_with_article}. "
                 f"Strokes gained stats, course fingerprint, and betting angles.")[:159]
    canonical = f"https://strokesedge.com/course-{slug}.html"

    html = template
    html = re.sub(r"<title>.*?</title>", f"<title>{title_tag}</title>", html, count=1)
    html = re.sub(r'<meta name="description" content=".*?">',
                  f'<meta name="description" content="{meta_desc}">', html, count=1)
    html = re.sub(r'<link rel="canonical" href=".*?">',
                  f'<link rel="canonical" href="{canonical}">', html, count=1)
    html = re.sub(r'<meta property="og:url" content=".*?">',
                  f'<meta property="og:url" content="{canonical}">', html, count=1)
    html = re.sub(r'<meta property="og:title" content=".*?">',
                  f'<meta property="og:title" content="{title_tag}">', html, count=1)
    html = re.sub(r'<meta property="og:description" content=".*?">',
                  f'<meta property="og:description" content="{meta_desc}">', html, count=1)
    html = re.sub(r'<meta name="twitter:title" content=".*?">',
                  f'<meta name="twitter:title" content="{title_tag}">', html, count=1)
    html = re.sub(r'<meta name="twitter:description" content=".*?">',
                  f'<meta name="twitter:description" content="{meta_desc}">', html, count=1)

    html = html.replace(
        '  <a href="courses.html">Course Guides</a>\n  <span>›</span>\n  Quail Hollow Club',
        f'  <a href="courses.html">Course Guides</a>\n  <span>›</span>\n  {course}',
    )
    html = html.replace(
        '<div class="course-tag"><div class="course-tag-dot"></div>Course Guide — Truist Championship</div>',
        f'<div class="course-tag"><div class="course-tag-dot"></div>Course Guide — {tourn}</div>',
    )
    html = re.sub(r'<h1 class="hero-title">.*?</h1>', f'<h1 class="hero-title">{course}</h1>',
                  html, count=1, flags=re.S)

    hero_meta = f"{location} · Par {par} · {yardage} yards · Hosts: {tourn}"
    html = re.sub(r'<div class="hero-meta">.*?</div>', f'<div class="hero-meta">{hero_meta}</div>',
                  html, count=1, flags=re.S)

    if analysis_failed:
        hero_sub = "Full analysis coming soon."
    else:
        sections = split_analysis_into_sections(analysis_text)
        overview = sections.get("course") or sections.get("full", analysis_text)
        hero_sub = overview.split("\n\n")[0][:400]
    html = re.sub(r'<p class="hero-sub">.*?</p>', f'<p class="hero-sub">{hero_sub}</p>',
                  html, count=1, flags=re.S)

    facts = [(f"Par {par}", "Course<br>Par"), (yardage, "Typical<br>Yardage")]
    # "$0" is what PGA Tour's feed returns for events it doesn't carry
    # purse data for (e.g. The Open Championship, an R&A event) — found
    # by running against a real major, not a hypothetical. Treat it as
    # "no data" the same as an empty string.
    if details.get("purse") and details["purse"] not in ("$0", "$0.00"):
        facts.append((details["purse"], "Purse"))
    facts_html = "\n  ".join(
        f'<div class="fact"><div class="fact-n">{v}</div><div class="fact-l">{l}</div></div>'
        for v, l in facts
    )
    # Non-greedy .*?</div> stops at the FIRST nested closing div it finds
    # (inside the first .fact child), not the end of the facts-bar block
    # — confirmed by running this against real template content, which
    # left 5 of the original template's 6 fact divs dangling after the
    # replacement. facts-bar is always immediately followed by a
    # <div class="divider"></div> in this template family (verified
    # against course-quail-hollow.html), so anchor on that instead of
    # trying to count nested divs with regex.
    html = re.sub(
        r'<div class="facts-bar">.*?(?=<div class="divider">)',
        f'<div class="facts-bar">\n  {facts_html}\n</div>\n\n', html, count=1, flags=re.S,
    )

    # Replace the 6 analytical <section> blocks (leave the trailing "More
    # from StrokesEdge" related-links section untouched).
    if analysis_failed:
        section_body = (
            '<div class="callout red"><div class="callout-label">Analysis pending</div>'
            '<div class="callout-text">Full analysis coming soon.</div></div>'
        )
        section_bodies = [section_body] * 6
    else:
        sections = split_analysis_into_sections(analysis_text)
        if "full" in sections:
            paras = "".join(f"<p class=\"body-text\">{p.strip()}</p>\n" for p in analysis_text.split("\n\n") if p.strip())
            section_bodies = [paras] + [
                '<div class="callout"><div class="callout-text">See course overview above — '
                'the model did not return clearly separated sections this run.</div></div>'
            ] * 5
        else:
            order = ["course", "primary", "what", "historical", "key", "course"]
            section_bodies = []
            for key in order:
                text = sections.get(key, "")
                paras = "".join(f'<p class="body-text">{p.strip()}</p>\n' for p in text.split("\n\n") if p.strip())
                section_bodies.append(paras or '<p class="body-text">[No content returned for this section.]</p>')

    labels = [
        ("01 — Course Fingerprint", "What the course actually demands."),
        ("02 — Predictive Stats", "What the data says actually matters."),
        ("03 — Winner DNA", "The filters every champion passes."),
        ("04 — Key Holes", "Where tournaments are decided."),
        ("05 — Historical Trends", "What recent history tells us."),
        ("06 — Betting Angles", f"How to bet {course} smart."),
    ]
    section_pattern = re.compile(r"<section>.*?</section>", re.S)
    matches = list(section_pattern.finditer(html))
    for i, ((num, title), body) in enumerate(zip(labels, section_bodies)):
        if i < len(matches) - 1:  # keep the final "More from StrokesEdge" section
            new_section = f'<section>\n  <div class="sec-num">{num}</div>\n  <h2>{title}</h2>\n  {body}\n</section>'
            html = html.replace(matches[i].group(0), new_section, 1)

    html = re.sub(
        r'<h2 class="cta-title">Get the full <span>.*?</span> breakdown\.</h2>',
        f'<h2 class="cta-title">Get the full <span>{tourn}</span> breakdown.</h2>',
        html, count=1,
    )

    return html, has_bom, had_crlf


def extract_top_stat_and_insight(analysis_text: str, analysis_failed: bool) -> tuple:
    """Best-effort extraction of a '#1 predictor' label and one-sentence
    insight for the courses.html card. Falls back to generic placeholders
    if the analysis text doesn't parse cleanly — never fabricates a
    specific stat that wasn't actually in the model output."""
    if analysis_failed:
        return "TBD", "Full analysis coming soon."
    sections = split_analysis_into_sections(analysis_text)
    stats_text = sections.get("what", sections.get("full", analysis_text))
    first_line = next((l.strip() for l in stats_text.split("\n") if l.strip()), "")
    top_stat = "SG: Approach"
    for cat in ("SG: Off the Tee", "SG: Approach", "SG: Around the Green", "SG: Putting"):
        if cat.split(": ")[1].lower() in first_line.lower():
            top_stat = cat
            break
    insight_source = sections.get("key", sections.get("full", analysis_text))
    insight = next((p.strip() for p in insight_source.split("\n\n") if p.strip()), "")
    insight_sentence = re.split(r"(?<=[.!?])\s", insight.strip())[0] if insight else "See full guide for model breakdown."
    return top_stat, insight_sentence[:200]


# ─────────────────────────────────────────────────────────────────────────
# STEP 5 — courses.html: swap old top badge, insert new card
# ─────────────────────────────────────────────────────────────────────────
def update_courses_index(details: dict, top_stat: str, insight: str) -> tuple:
    text, has_bom, had_crlf = read_text(COURSES_INDEX_FILE)
    slug = details["slug"]

    # A run for a course that's already in the grid (re-run, overlapping
    # instance, etc.) must not insert another copy of its card.
    if f'href="course-{slug}.html"' in text:
        logger.info(f"courses.html already has a card for course-{slug}.html — skipping duplicate insert")
        return text, has_bom, had_crlf

    # "Guide live" is not a unique "current tournament" marker — multiple
    # cards can carry it at once (verified: 4 do, as of writing this).
    # What actually needs to flip is specifically the CURRENT TOP card,
    # since the new card always gets inserted above it. Operate on that
    # card positionally (the first .course-card block in the grid), not
    # on whichever card happens to match the badge text first in the
    # file — those aren't guaranteed to be the same card.
    grid_marker = '<div class="courses-grid" id="courses-grid">'
    grid_start = text.find(grid_marker)
    if grid_start == -1:
        raise RuntimeError("Could not find #courses-grid in courses.html")
    first_card_match = re.search(r'<a href="course-[^"]+\.html"[^>]*class="course-card[^>]*>.*?</a>',
                                  text[grid_start:], re.S)
    if first_card_match:
        old_card = first_card_match.group(0)
        if "badge-live" in old_card:
            new_card = old_card.replace(
                '<span class="card-badge badge-live">Guide live</span>',
                '<span class="card-badge">Archive</span>', 1,
            )
            text = text[:grid_start] + text[grid_start:].replace(old_card, new_card, 1)
        else:
            logger.info("Current top course-card has no 'Guide live' badge to archive — leaving it as-is")
    else:
        logger.info("No existing course-card found in the grid — nothing to archive (first run?)")

    card = (
        f'\n    <!-- {details["course_name"]} — auto-generated {date.today().isoformat()} -->\n'
        f'    <a href="course-{slug}.html" class="course-card featured" data-tags="new">\n'
        f'      <div class="card-header">\n'
        f'        <div>\n'
        f'          <div class="card-tournament">{details["tournament_name"]} · {details["location"]}</div>\n'
        f'          <div class="card-name">{details["course_name"]}</div>\n'
        f'          <div class="card-location">Par {details["par"]} · {details["yardage"]} yards</div>\n'
        f'        </div>\n'
        f'        <span class="card-badge badge-live">Guide live</span>\n'
        f'      </div>\n'
        f'      <div class="card-body">\n'
        f'        <div class="card-stats">\n'
        f'          <div class="cs-item"><div class="cs-val">#1</div><div class="cs-label">{top_stat}</div></div>\n'
        f'          <div class="cs-item"><div class="cs-val">{details["course_type"].split("/")[0].title()}</div><div class="cs-label">Course type</div></div>\n'
        f'        </div>\n'
        f'        <div class="card-predictor"><strong>Key model insight:</strong> {insight}</div>\n'
        f'      </div>\n'
        f'      <div class="card-footer">\n'
        f'        <div class="card-date">{details["tournament_name"]} · {details["dates"]}</div>\n'
        f'        <div class="card-link">Read guide →</div>\n'
        f'      </div>\n'
        f'    </a>\n'
    )
    marker = '<div class="courses-grid" id="courses-grid">'
    if marker not in text:
        raise RuntimeError("Could not find #courses-grid in courses.html")
    text = text.replace(marker, marker + card, 1)
    return text, has_bom, had_crlf


# ─────────────────────────────────────────────────────────────────────────
# STEP 6 — sitemap.xml
# ─────────────────────────────────────────────────────────────────────────
def update_sitemap(slug: str) -> tuple:
    text, has_bom, had_crlf = read_text(SITEMAP_FILE)

    if f"course-{slug}.html</loc>" in text:
        logger.info(f"sitemap.xml already has an entry for course-{slug}.html — skipping duplicate insert")
        return text, has_bom, had_crlf

    entry = (
        f'  <url>\n'
        f'    <loc>https://strokesedge.com/course-{slug}.html</loc>\n'
        f'    <lastmod>{date.today().isoformat()}</lastmod>\n'
        f'    <changefreq>yearly</changefreq>\n'
        f'    <priority>0.8</priority>\n'
        f'  </url>\n\n'
    )
    marker = "  <url>\n    <loc>https://strokesedge.com/courses.html</loc>"
    idx = text.find(marker)
    if idx == -1:
        raise RuntimeError("Could not find courses.html entry in sitemap.xml")
    close_idx = text.find("</url>", idx) + len("</url>\n\n")
    return text[:close_idx] + entry + text[close_idx:], has_bom, had_crlf


# ─────────────────────────────────────────────────────────────────────────
# Git
# ─────────────────────────────────────────────────────────────────────────
def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=check,
                           capture_output=True, text=True)


def git_commit_local(new_page_relpath: str, tourn: str, dates: str) -> bool:
    git("add", new_page_relpath, "Strokes Edge Website HTML/courses.html",
        "Strokes Edge Website HTML/sitemap.xml", "weekly_course_update.log")
    status = git("status", "--short").stdout
    if not status.strip():
        logger.info("Nothing staged — skipping commit")
        return False
    message = f"Auto: Add {tourn} course page — {dates}"
    git("commit", "-m", message)
    logger.info(f"Committed locally: {message}")
    return True


def git_push() -> bool:
    result = git("push", "origin", "main", check=False)
    if result.returncode != 0:
        logger.error(f"git push failed: {result.stderr}")
        return False
    logger.info("Pushed to GitHub — Cloudflare Pages will deploy within ~60 seconds.")
    return True


# ─────────────────────────────────────────────────────────────────────────
# Email
# ─────────────────────────────────────────────────────────────────────────
def send_email(subject: str, body: str) -> None:
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not app_password:
        logger.error("GMAIL_APP_PASSWORD not set — skipping email notification")
        return
    to_addr = "strokesedge@gmail.com"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = to_addr
    msg["To"] = to_addr
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(to_addr, app_password)
            server.sendmail(to_addr, [to_addr], msg.as_string())
        logger.info(f"Email sent: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


# ─────────────────────────────────────────────────────────────────────────
# Concurrency guard
# ─────────────────────────────────────────────────────────────────────────
class AlreadyRunningError(Exception):
    pass


def acquire_lock() -> None:
    """Refuse to proceed if another instance holds the lock.

    Closes the gap Task Scheduler's own MultipleInstances=IgnoreNew setting
    can't: a fresh launch can slip through if it lands before Task Scheduler
    has finished marking the prior instance as Running (this script exits
    its early steps in well under a second, so rapid manual re-clicks can
    land inside that window). The os.open(..., O_CREAT | O_EXCL) call is an
    atomic exclusive-create at the OS level, so only one process can ever
    win it, no matter how close together two launches are.
    """
    if LOCK_FILE.exists():
        age = time.time() - LOCK_FILE.stat().st_mtime
        if age < LOCK_STALE_SECONDS:
            raise AlreadyRunningError(
                f"Lock file is {age:.0f}s old — another instance appears to be running."
            )
        logger.info(f"Removing stale lock file (age {age:.0f}s, over {LOCK_STALE_SECONDS}s threshold)")
        LOCK_FILE.unlink()

    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise AlreadyRunningError("Another instance won the lock first.")
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)


def release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────
def run(test_mode: bool) -> None:
    logger.info("=" * 70)
    logger.info(f"Run started {datetime.now().isoformat()} (test_mode={test_mode})")

    try:
        tournaments = fetch_pga_schedule()
        tournament = pick_next_tournament(tournaments)
        logger.info(f"Next tournament: {tournament['name']} ({tournament.get('displayDate')})")
    except Exception as e:
        logger.error(f"FATAL: could not determine next tournament: {e}")
        if not test_mode:
            send_email("StrokesEdge: Weekly course update FAILED — schedule fetch failed",
                       f"Could not fetch or parse the tournament schedule. No files were touched.\n\nError: {e}")
        sys.exit(1)

    try:
        details = get_course_details(tournament)
        details["slug"] = slugify(details["course_name"])
    except Exception as e:
        logger.error(f"FATAL: could not get course details: {e}")
        if not test_mode:
            send_email("StrokesEdge: Weekly course update FAILED — course detail fetch failed",
                       f"Found tournament '{tournament.get('name')}' but could not resolve its "
                       f"course details. No files were touched.\n\nError: {e}")
        sys.exit(1)

    logger.info(f"Course: {details['course_name']} | {details['location']} | "
               f"Par {details['par']} | {details['yardage']} yds | slug={details['slug']}")

    new_page_path = SITE_DIR / f"course-{details['slug']}.html"
    page_already_exists = new_page_path.exists()
    if page_already_exists:
        logger.info(f"course-{details['slug']}.html already exists — will still refresh "
                   f"courses.html card and sitemap, but will NOT overwrite the page.")

    analysis_text = None
    analysis_failed = True
    if not page_already_exists:
        analysis_text = generate_analysis(details)
        analysis_failed = analysis_text is None
        if analysis_failed:
            logger.error("Claude API call failed — falling back to a minimal factual page "
                        '(par/yardage/location/dates only, "Full analysis coming soon").')

    try:
        if not page_already_exists:
            course_html, course_bom, course_crlf = build_course_page(details, analysis_text, analysis_failed)
        top_stat, insight = extract_top_stat_and_insight(analysis_text, analysis_failed)
        courses_index_html, index_bom, index_crlf = update_courses_index(details, top_stat, insight)
        sitemap_html, sitemap_bom, sitemap_crlf = update_sitemap(details["slug"])
    except Exception as e:
        logger.error(f"FATAL: page generation failed: {e}")
        if not test_mode:
            send_email("StrokesEdge: Weekly course update FAILED — page generation failed",
                       f"Scraping succeeded but generating the page/index/sitemap content "
                       f"failed. No files were written.\n\nError: {e}")
        sys.exit(1)

    if test_mode:
        print("\n" + "=" * 70)
        print("TEST MODE — nothing written, nothing committed, no email sent")
        print("=" * 70)
        if not page_already_exists:
            print(f"\n--- Would write {new_page_path.name} ---\n")
            print(course_html[:3000] + ("\n...(truncated)..." if len(course_html) > 3000 else ""))
        print(f"\n--- courses.html card would use: top_stat={top_stat!r}, insight={insight!r} ---")
        print(f"\n--- sitemap.xml would gain an entry for course-{details['slug']}.html ---")
        return

    try:
        if not page_already_exists:
            write_text(new_page_path, course_html, course_bom, course_crlf)
        write_text(COURSES_INDEX_FILE, courses_index_html, index_bom, index_crlf)
        write_text(SITEMAP_FILE, sitemap_html, sitemap_bom, sitemap_crlf)
    except Exception as e:
        logger.error(f"FATAL: file write failed, aborting before any git action: {e}")
        send_email("StrokesEdge: Weekly course update FAILED — file write failed",
                   f"Generated content successfully but writing files failed. "
                   f"No git commit was made.\n\nError: {e}")
        sys.exit(1)

    logger.info(f"Wrote/updated: "
               f"{'course-' + details['slug'] + '.html, ' if not page_already_exists else ''}"
               f"courses.html, sitemap.xml")

    try:
        committed = git_commit_local(
            (new_page_path if not page_already_exists else COURSES_INDEX_FILE).relative_to(REPO_ROOT).as_posix(),
            details["tournament_name"], details["dates"],
        )
    except Exception as e:
        logger.error(f"FATAL: git commit failed: {e}")
        send_email("StrokesEdge: Weekly course update FAILED — git commit failed",
                   f"Files were written successfully but the git commit step failed "
                   f"(possibly a lock conflict from an overlapping run). "
                   f"courses.html/sitemap.xml on disk may be ahead of the last commit — "
                   f"check `git status` before the next run.\n\nError: {e}")
        sys.exit(1)

    if AUTO_PUSH and committed:
        try:
            git_push()
            push_note = "Pushed automatically (AUTO_PUSH=True)."
        except Exception as e:
            logger.error(f"FATAL: git push failed: {e}")
            send_email("StrokesEdge: Weekly course update FAILED — git push failed",
                       f"Commit succeeded locally but the push step failed.\n\n"
                       f"Run `python weekly_course_update.py --push` manually.\n\nError: {e}")
            sys.exit(1)
    else:
        push_note = ("Held locally — review the commit, then run:\n"
                     "    python weekly_course_update.py --push")

    summary = (
        f"Tournament: {tournament['name']} ({details['dates']})\n"
        f"Course: {details['course_name']}, {details['location']}\n"
        f"Page: course-{details['slug']}.html "
        f"{'(already existed — not overwritten)' if page_already_exists else '(new)'}\n"
        f"Claude analysis: {'FAILED — minimal placeholder page used' if analysis_failed else 'generated'}\n\n"
        f"{push_note}\n"
    )
    logger.info(summary)

    subject = (f"StrokesEdge: {tournament['name']} course page is live"
               if (AUTO_PUSH and committed) else
               f"StrokesEdge: {tournament['name']} course page ready for review")
    send_email(subject, summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--test", action="store_true",
                        help="Scrape and generate but write nothing, commit nothing, email nothing")
    parser.add_argument("--push", action="store_true",
                        help="Push whatever is already locally committed. Does nothing else.")
    args = parser.parse_args()

    try:
        acquire_lock()
    except AlreadyRunningError as e:
        logger.info(f"Exiting without running — {e}")
        return
    atexit.register(release_lock)

    if args.push:
        logger.info("=" * 70)
        logger.info(f"--push invoked {datetime.now().isoformat()}")
        pending = git("log", "origin/main..HEAD", "--oneline", check=False).stdout.strip()
        if not pending:
            print("No local commits ahead of origin/main — nothing to push.")
            return
        print("Pending commit(s):\n" + pending)
        if git_push():
            print("Pushed.")
        else:
            sys.exit(1)
        return

    run(test_mode=args.test)


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════════════════
# SETUP INSTRUCTIONS
# ═══════════════════════════════════════════════════════════════════════
#
# 1. ANTHROPIC_API_KEY (Windows environment variable)
#    ------------------------------------------------
#    PowerShell (persists across reboots, current user only):
#        [System.Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', 'sk-ant-...', 'User')
#    Or via GUI: Settings > System > About > Advanced system settings >
#    Environment Variables > New (under "User variables").
#    Restart any open terminal / Task Scheduler won't see it until you do.
#
# 2. GMAIL_APP_PASSWORD (Windows environment variable)
#    ---------------------------------------------------
#    Gmail app passwords require 2-Step Verification enabled on the
#    account first (myaccount.google.com/security).
#    Then: myaccount.google.com/apppasswords > create one named
#    "strokesedge-script" > copy the 16-character password (no spaces).
#        [System.Environment]::SetEnvironmentVariable('GMAIL_APP_PASSWORD', 'xxxxxxxxxxxxxxxx', 'User')
#    This sends FROM and TO strokesedge@gmail.com — the app password must
#    belong to that account.
#
# 3. GitHub push authentication
#    ---------------------------
#    This script calls plain `git push` via subprocess — it does not read
#    Windows Credential Manager itself. If `git push` already works when
#    you type it manually in this repo (which it does, since you've been
#    pushing all session), it will work identically here, using whatever
#    credential helper is already configured (Git Credential Manager, a
#    stored PAT, or SSH key) — nothing extra to set up.
#
# 4. Windows Task Scheduler — run every Sunday at 5pm
#    -------------------------------------------------
#    a. Open Task Scheduler > Create Task (not "Basic Task" — you need
#       the "Run whether user is logged on or not" option).
#    b. General tab: name it "StrokesEdge Weekly Course Update". Check
#       "Run whether user is logged on or not".
#    c. Triggers tab > New: Weekly, Sunday, 5:00:00 PM.
#    d. Actions tab > New:
#         Program/script:  C:\\path\\to\\python.exe
#         Arguments:       weekly_course_update.py
#         Start in:        C:\\Users\\bkopp\\strokesedge-site
#       (Use the full path to python.exe from `where python` — Task
#       Scheduler does not use your shell's PATH.)
#    e. Conditions tab: uncheck "Start the task only if the computer is
#       on AC power" if this runs on a laptop.
#    f. Save. Test it immediately via Task Scheduler > right-click the
#       task > Run, then check weekly_course_update.log.
#    Remember: this only commits locally (see the docstring at the top of
#    this file). Nothing publishes until you separately run
#    `python weekly_course_update.py --push`.
#
# 5. Test mode
#    ---------
#        python weekly_course_update.py --test
#    Scrapes pgatour.com and Wikipedia, calls the Claude API, and prints
#    everything it would do to the terminal. Writes no files, makes no
#    git commit, sends no email. Safe to run repeatedly.
# ═══════════════════════════════════════════════════════════════════════
