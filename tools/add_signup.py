"""
Wire the on-site signup (se-signup.js) into every page. Safe to re-run.

- Any link to the bare Substack publication (https://strokesedge.substack.com) gets a
  data-signup attribute, so it opens the signup dialog on the site. The href stays as the
  no-JavaScript fallback. Links to individual Substack posts are left alone.
- Adds <script src="se-signup.js" defer> before </body> on every page that lacks it.
Run after building new pages by hand, or whenever a page is missing the script.
"""
import glob
import os
import re

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Strokes Edge Website HTML")
SCRIPT = '<script src="se-signup.js" defer></script>'
LINK = re.compile(r'<a\b([^>]*?)href="https://strokesedge\.substack\.com/?"([^>]*)>')

changed = links = 0
for path in sorted(glob.glob(os.path.join(SITE, "*.html"))):
    name = os.path.basename(path)
    if name == "favicon-head-snippet.html":
        continue
    s = open(path, encoding="utf-8", newline="").read()

    def repl(m):
        global links
        if "data-signup" in m.group(0):
            return m.group(0)
        links += 1
        return '<a%shref="https://strokesedge.substack.com"%s data-signup>' % (m.group(1), m.group(2))

    t = LINK.sub(repl, s)
    if "se-signup.js" not in t and "</body>" in t:
        t = t.replace("</body>", SCRIPT + "\n</body>", 1)
    if t != s:
        open(path, "w", encoding="utf-8", newline="").write(t)
        changed += 1
print("pages changed:", changed, "| links wired:", links)
