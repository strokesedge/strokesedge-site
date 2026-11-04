"""
Site audit: checks the rules that keep the site consistent, on every page. Exit code 1 if anything fails.
    python tools/audit_site.py          (prints problems, or "OK")
It runs at the end of weekly_site_update.py prepare, so a re-run tool that regresses an earlier decision
is caught before anything is committed.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "Strokes Edge Website HTML")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKIP = {"favicon-head-snippet.html"}
problems = []


def bad(page, msg):
    problems.append("%s: %s" % (page, msg))


pages = sorted(os.path.basename(p) for p in glob.glob(os.path.join(SITE, "*.html")) if os.path.basename(p) not in SKIP)
sitemap = open(os.path.join(SITE, "sitemap.xml"), encoding="utf-8").read()
locs = set(re.findall(r"<loc>https://strokesedge\.com/?([^<]*)</loc>", sitemap))

for name in pages:
    h = open(os.path.join(SITE, name), encoding="utf-8").read()
    stem = name[:-5]
    if "<title>" not in h or 'name="description"' not in h:
        bad(name, "missing title or description")
    can = re.search(r'rel="canonical" href="([^"]*)"', h)
    if not can:
        bad(name, "no canonical")
    elif can.group(1).endswith(".html"):
        bad(name, "canonical ends in .html")
    if 'og:title' not in h or 'twitter:card' not in h:
        bad(name, "missing OG/Twitter tags")
    if "G-D398EHRP6Y" not in h:
        bad(name, "missing GA4")
    if name != "index.html" and "se-theme.css" not in h:
        bad(name, "theme css not linked")
    if "se-signup.js" not in h:
        bad(name, "signup script missing")
    if "Gamble responsibly" not in h:
        bad(name, "footer disclaimer missing")
    if "max-width:860px" not in h or "max-width:640px" not in h:
        bad(name, "responsive breakpoints missing")
    if name != "404.html":
        nav = re.search(r"<nav\b.*?</nav>", h, re.S)
        navt = nav.group(0) if nav else ""
        for label, href in (("Pick Tracker", "picks.html"), ("Guides", "pga-tour-betting-guide.html")):
            if label not in navt or href not in navt:
                bad(name, "nav is missing %s" % label)
        if "results.html" in h:
            bad(name, "still links to the removed results.html")
        if 'href="privacy.html"' not in h or 'href="terms.html"' not in h:
            bad(name, "footer is missing Privacy/Terms")
    if re.match(r"(analysis|course)-", name) and ("og/%s.png" % stem) not in h:
        bad(name, "no page-specific social image")
    if "potd.html" in h:
        bad(name, "references potd.html")
    for link in re.findall(r'href="([^"#?]+)"', h):
        if link.startswith(("http", "mailto:", "tel:", "/", "javascript")):
            continue
        if not (os.path.exists(os.path.join(SITE, link)) or os.path.exists(os.path.join(SITE, link + ".html"))):
            bad(name, "broken link: " + link)
    if name not in ("404.html", "index.html") and stem not in locs:
        bad(name, "not in sitemap.xml")

for loc in locs:
    if loc and not os.path.exists(os.path.join(SITE, loc + ".html")) and loc not in ("",):
        bad("sitemap.xml", "lists a page that does not exist: " + loc)

if problems:
    print("AUDIT: %d problem(s)" % len(problems))
    for p in problems[:40]:
        print(" -", p)
    sys.exit(1)
print("AUDIT OK: %d pages, no problems" % len(pages))
