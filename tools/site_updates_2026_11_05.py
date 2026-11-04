"""
One-off site-wide updates applied 2026-11-05 (kept for reference, safe to re-run):

The public results page is merged into the Pick Tracker (picks.html), so:
  * nav: "Results" goes back to "Pick Tracker" (picks.html), on desktop nav and mobile menu
  * every other link to results.html now points at picks.html; duplicate footer entries are removed
  * results.html is deleted, /results and /results.html redirect (301) to /picks, sitemap entry removed
  * the tool sources that mention results.html are updated
"""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "Strokes Edge Website HTML")
stats = {"nav": 0, "footer_removed": 0, "links": 0}

NAV_SPANS = [
    re.compile(r"<nav\b.*?</nav>", re.S),
    re.compile(r'<div class="mobile-menu"[^>]*>.*?</div>', re.S),
    re.compile(r'<div class="mob"[^>]*>.*?</div>', re.S),
]
NAV_LINK = re.compile(r'<a href="results\.html"([^>]*)>Results</a>')
FOOT_RESULTS = '<a href="results.html">Results</a>'
FOOT_PICKS = '<a href="picks.html">Pick Tracker</a>'


def fix(name, s):
    def link_repl(m):
        attrs = re.sub(r"\s*\bactive\b", "", m.group(1)).replace('class=""', "")
        if name == "picks.html" and 'class="nav-link"' in attrs:
            attrs = attrs.replace('class="nav-link"', 'class="nav-link active"')
        return '<a href="picks.html"%s>Pick Tracker</a>' % attrs

    for span in NAV_SPANS:
        t = span.sub(lambda m: NAV_LINK.sub(link_repl, m.group(0)), s)
        if t != s:
            stats["nav"] += 1
            s = t
    # footers: a plain Results link duplicates the Pick Tracker link, drop it (or convert it if there is none)
    if FOOT_RESULTS in s:
        if FOOT_PICKS in s:
            s = s.replace(FOOT_RESULTS, "")
            stats["footer_removed"] += 1
        else:
            s = s.replace(FOOT_RESULTS, FOOT_PICKS)
    # remaining links and wording
    n = s.count('href="results.html"')
    if n:
        s = s.replace('href="results.html"', 'href="picks.html"')
        stats["links"] += n
    s = s.replace("StrokesEdge results page", "StrokesEdge pick tracker").replace("public results page", "public pick tracker")
    s = re.sub(r'(<a href="picks\.html"[^>]*>)Results(<small>)', r"\1Pick Tracker\2", s)
    return s


for path in sorted(glob.glob(os.path.join(SITE, "*.html"))):
    name = os.path.basename(path)
    if name in ("favicon-head-snippet.html", "results.html"):
        continue
    s = open(path, encoding="utf-8", newline="").read()
    t = fix(name, s)
    if t != s:
        open(path, "w", encoding="utf-8", newline="").write(t)

# results.html -> removed, redirected
res = os.path.join(SITE, "results.html")
if os.path.exists(res):
    os.remove(res)

red = os.path.join(SITE, "_redirects")
r = open(red, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in r else "\n"
if "/results" not in r:
    r = r.rstrip() + nl + "/results     /picks  301" + nl + "/results.html   /picks  301" + nl
    open(red, "w", encoding="utf-8", newline="").write(r)

sm = os.path.join(SITE, "sitemap.xml")
s = open(sm, encoding="utf-8", newline="").read()
s2 = re.sub(r"[ \t]*<url>\s*<loc>https://strokesedge\.com/results</loc>.*?</url>\s*", "", s, flags=re.S)
if s2 != s:
    open(sm, "w", encoding="utf-8", newline="").write(s2)

# tool sources
for rel, pairs in {
    "tools/build_tool_pages.py": [('("results.html", "Results", "Every bet, wins and losses")', '("picks.html", "Pick Tracker", "Every bet, wins and losses")')],
    "tools/publish_picks.py": [('<a href="results.html">See the public record</a>', '<a href="picks.html">See the public record</a>')],
    "tools/cheat_sheet.html": [("strokesedge.com/results", "strokesedge.com/picks")],
}.items():
    p = os.path.join(ROOT, rel)
    t = open(p, encoding="utf-8", newline="").read()
    for a, b in pairs:
        t = t.replace(a, b)
    open(p, "w", encoding="utf-8", newline="").write(t)
print(stats, "| results.html exists:", os.path.exists(res))
