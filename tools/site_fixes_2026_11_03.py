"""
One-off site-wide fixes applied 2026-11-03 (kept for reference, safe to re-run):

1. Canonical URLs: Cloudflare Pages 308-redirects every NAME.html to /NAME, so the
   canonical, og:url and JSON-LD URLs in <head> and the sitemap <loc> entries must use
   the extensionless form. The homepage stays https://strokesedge.com/.
2. Main nav: add a "Guides" link (PGA Tour betting guide) after "Analysis", in both the
   desktop nav and the mobile menu.
"""
import glob
import os
import re

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Strokes Edge Website HTML")
HOST = "https://strokesedge.com/"
GUIDE = "pga-tour-betting-guide.html"

stats = {"canon": 0, "nav": 0, "mobile": 0}

URL_RE = re.compile(re.escape(HOST) + r"([a-z0-9\-]+)\.html")


def fix_head(s):
    i, j = s.find("<head>"), s.find("</head>")
    if i < 0 or j < 0:
        return s
    head = s[i:j]
    new = URL_RE.sub(lambda m: HOST if m.group(1) == "index" else HOST + m.group(1), head)
    if new != head:
        stats["canon"] += 1
    return s[:i] + new + s[j:]


def add_guides(s):
    """Insert a Guides link after every Analysis link in nav / mobile menu."""
    def repl(m):
        tag = m.group(0)
        if GUIDE in s[m.end():m.end() + 400]:
            return tag
        guide = tag.replace('href="analysis.html"', 'href="%s"' % GUIDE).replace(">Analysis<", ">Guides<")
        guide = re.sub(r"\s*\bactive\b", "", guide)
        guide = guide.replace('class=""', "").replace("  ", " ")
        return tag + guide
    return re.sub(r'<a href="analysis\.html"[^>]*>Analysis</a>', repl, s)


for path in sorted(glob.glob(os.path.join(SITE, "*.html"))):
    name = os.path.basename(path)
    if name == "favicon-head-snippet.html":
        continue
    s = open(path, encoding="utf-8", newline="").read()
    t = fix_head(s)
    before = t.count(GUIDE)
    t = add_guides(t)
    added = t.count(GUIDE) - before
    if added:
        stats["nav"] += 1
        stats["mobile"] += max(0, added - 1)
    if t != s:
        open(path, "w", encoding="utf-8", newline="").write(t)

# sitemap
sm = os.path.join(SITE, "sitemap.xml")
s = open(sm, encoding="utf-8", newline="").read()
# weekly_course_update.py accepts either form of the courses entry since 2026-11-03, so normalize everything.
t = re.sub(r"(<loc>" + re.escape(HOST) + r"[a-z0-9\-]+)\.html(</loc>)", lambda m: m.group(1) + m.group(2), s)
open(sm, "w", encoding="utf-8", newline="").write(t)
print(stats, "sitemap .html left:", t.count(".html"))
