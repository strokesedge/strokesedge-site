"""
One-off site-wide updates applied 2026-11-04 (kept for reference, safe to re-run):

1. Nav: the "Pick Tracker" link in the desktop nav and mobile menu now reads "Results" and points at the
   public results.html. picks.html (the access-code tracker) stays reachable from footers and the results page.
2. Analysis page gate: the old "your@email.com / Unlock" box never sent the email anywhere, so it implied a
   signup that did not happen. It becomes an honest "Already subscribed? Show the full breakdown" button.
   The real signup is the Subscribe button, which opens the on-site Substack dialog.
3. Footers: the "Weekly model" link points at the new membership page.
"""
import glob
import os
import re

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Strokes Edge Website HTML")
stats = {"nav": 0, "gate": 0, "footer": 0}

NAV_SPANS = [
    re.compile(r"<nav\b.*?</nav>", re.S),
    re.compile(r'<div class="mobile-menu"[^>]*>.*?</div>', re.S),
    re.compile(r'<div class="mob"[^>]*>.*?</div>', re.S),
]
LINK = re.compile(r'<a href="picks\.html"([^>]*)>Pick Tracker</a>')

FORM = re.compile(r'<form class="cliff-form" id="cliff-form">.*?</form>', re.S)
BUTTON = '<button type="button" class="cliff-link" id="cliff-unlock">Already subscribed? Show the full breakdown</button>'
GATE_JS = re.compile(r"// ── Content cliff gate ──.*?\}\)\(\);", re.S)
NEW_JS = (
    "// ── Content cliff gate ──\n"
    "(function(){\n"
    "  var overlay=document.getElementById('cliff-overlay');\n"
    "  var btn=document.getElementById('cliff-unlock');\n"
    "  var GATE_KEY='se_analysis_unlocked';\n"
    "  function isUnlocked(){\n"
    "    try{return sessionStorage.getItem(GATE_KEY)==='1';}catch(e){return false;}\n"
    "  }\n"
    "  function unlock(){\n"
    "    try{sessionStorage.setItem(GATE_KEY,'1');}catch(e){}\n"
    "    if(overlay)overlay.classList.add('hidden');\n"
    "  }\n"
    "  if(!isUnlocked()&&overlay){\n"
    "    overlay.classList.add('active');\n"
    "    if(btn)btn.addEventListener('click',unlock);\n"
    "  } else if(overlay){\n"
    "    overlay.classList.add('hidden');\n"
    "  }\n"
    "})();"
)


def fix_nav(name, s):
    def link_repl(m):
        attrs = m.group(1)
        if name == "picks.html":
            attrs = re.sub(r"\s*\bactive\b", "", attrs).replace('class=""', "")
        elif name == "results.html" and 'class="nav-link"' in attrs:
            attrs = attrs.replace('class="nav-link"', 'class="nav-link active"')
        return '<a href="results.html"%s>Results</a>' % attrs

    for span in NAV_SPANS:
        def span_repl(m):
            return LINK.sub(link_repl, m.group(0))
        s2 = span.sub(span_repl, s)
        if s2 != s:
            stats["nav"] += 1
            s = s2
    return s


for path in sorted(glob.glob(os.path.join(SITE, "*.html"))):
    name = os.path.basename(path)
    if name == "favicon-head-snippet.html":
        continue
    s = open(path, encoding="utf-8", newline="").read()
    t = s  # nav step retired 2026-11-05: Results was merged back into "Pick Tracker" (see site_updates_2026_11_05.py)
    if FORM.search(t):
        t = FORM.sub(lambda m: BUTTON, t)
        t = GATE_JS.sub(lambda m: NEW_JS, t)
        stats["gate"] += 1
    t2 = t.replace('<a href="https://strokesedge.gumroad.com/l/buehoc" target="_blank" rel="noopener">Weekly model</a>',
                   '<a href="membership.html">Membership</a>')
    if t2 != t:
        stats["footer"] += 1
        t = t2
    if t != s:
        open(path, "w", encoding="utf-8", newline="").write(t)
print(stats)
