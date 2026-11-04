"""
Generate a 1200x630 social-share image for every analysis and course page, plus the
default og-image.png, and point each page's og:image / twitter:image at its own image.

Run from anywhere:  python tools/make_og_images.py [--force] [--only slug-substring]
Needs Google Chrome (headless) and internet access for the Google Fonts. Images land in
"Strokes Edge Website HTML/og/<page-slug>.png". Existing images are kept unless --force.
Add this to the weekly update: after creating the new analysis and course pages, run it.
"""
import glob
import html
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "Strokes Edge Website HTML")
OUT = os.path.join(SITE, "og")
CHROME = os.environ.get("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
HOST = "https://strokesedge.com/"

TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,300..900&family=DM+Mono:wght@400;500&family=Instrument+Serif:ital@0;1&display=swap">
<style>
*{box-sizing:border-box;margin:0}
html,body{width:1200px;height:630px;overflow:hidden;background:#050807}
body{position:relative;font-family:'Archivo',sans-serif;color:#e8efe9}
.glow{position:absolute;right:-220px;top:-120px;width:900px;height:900px;background:radial-gradient(closest-side,rgba(0,230,118,.28),rgba(0,230,118,.08) 50%,transparent 72%)}
.ball{position:absolute;right:70px;top:150px;width:330px;height:330px;border-radius:50%;
 background:radial-gradient(circle at 34% 30%,#fff 0,#f1efe8 38%,#cfcbbf 70%,#8d8a80 100%);
 box-shadow:0 0 120px rgba(0,230,118,.38),inset -26px -30px 60px rgba(0,0,0,.28)}
.ball::after{content:'';position:absolute;inset:0;border-radius:50%;opacity:.5;
 background-image:radial-gradient(circle at 50% 50%,rgba(0,0,0,.17) 0 5px,transparent 6px),radial-gradient(circle at 50% 50%,rgba(0,0,0,.17) 0 5px,transparent 6px);background-size:26px 26px;background-position:0 0,13px 13px}
.ring{position:absolute;right:14px;top:92px;width:440px;height:440px;border-radius:50%;border:2px solid rgba(0,230,118,.55);transform:rotate(-18deg) scaleY(.34)}
.wrap{position:absolute;left:72px;top:64px;right:470px;bottom:64px;display:flex;flex-direction:column}
.eyebrow{font:500 22px/1 'DM Mono',monospace;letter-spacing:.16em;text-transform:uppercase;color:#00e676;margin-bottom:34px}
h1{font-weight:800;font-stretch:108%;letter-spacing:-.03em;line-height:.95;text-wrap:balance}
h1 em{font:italic 400 1em/.95 'Instrument Serif',serif;color:#00e676;letter-spacing:-.01em}
.meta{margin-top:30px;font:400 22px/1.5 'DM Mono',monospace;color:#8da398;max-width:640px}
.brand{margin-top:auto;display:flex;align-items:center;justify-content:space-between;font:800 34px/1 'Archivo',sans-serif;font-stretch:118%;letter-spacing:-.02em}
.brand b{color:#00e676}
.brand span{font:400 20px/1 'DM Mono',monospace;color:#8da398;letter-spacing:.08em}
</style></head><body>
<div class="glow"></div><div class="ring"></div><div class="ball"></div>
<div class="wrap">
<div class="eyebrow">__EYEBROW__</div>
<h1 style="font-size:__SIZE__px">__TITLE__</h1>
<div class="meta">__META__</div>
<div class="brand"><div>Strokes<b>Edge</b></div><span>strokesedge.com</span></div>
</div></body></html>"""


def clean(x):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(x))).strip()


def info(path):
    s = open(path, encoding="utf-8").read()
    name = os.path.basename(path)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    h1 = clean(h1.group(1)) if h1 else clean(re.search(r"<title>(.*?)</title>", s).group(1)).split(" \u2014 ")[0]
    h1 = h1.rstrip(". ")
    meta = re.search(r'<div class="hero-meta[^"]*"[^>]*>(.*?)</div>', s, re.S)
    meta = clean(meta.group(1)) if meta else ""
    if name.startswith("course-"):
        eyebrow, title = "Course betting guide", h1 + " <em>betting guide</em>"
    else:
        year = re.search(r"(20\d\d)", name)
        eyebrow = "%s analysis" % (year.group(1) if year else "Tournament")
        title = h1
        title = re.sub(r"\s*20\d\d$", "", title)
    parts, out = meta.split(" · "), ""
    for part in parts:
        nxt = part if not out else out + " · " + part
        if len(nxt) > 96:
            break
        out = nxt
    return eyebrow, title, out or meta[:96]


def render(eyebrow, title, meta, out_png):
    plain = re.sub(r"<[^>]+>", "", title)
    size = 112 if len(plain) <= 20 else 92 if len(plain) <= 30 else 76 if len(plain) <= 42 else 62
    doc = (TEMPLATE.replace("__EYEBROW__", html.escape(eyebrow)).replace("__TITLE__", title)
           .replace("__META__", html.escape(meta)).replace("__SIZE__", str(size)))
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(doc)
        tmp = f.name
    try:
        subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--window-size=1200,630",
                        "--virtual-time-budget=6000", "--screenshot=" + out_png,
                        "file:///" + tmp.replace("\\", "/")],
                       check=True, capture_output=True, timeout=90)
    finally:
        os.unlink(tmp)


def point_page(path, slug):
    s = open(path, encoding="utf-8", newline="").read()
    url = HOST + "og/%s.png" % slug
    t = re.sub(r'(<meta property="og:image" content=")[^"]*', lambda m: m.group(1) + url, s, count=1)
    t = re.sub(r'(<meta name="twitter:image" content=")[^"]*', lambda m: m.group(1) + url, t, count=1)
    if 'property="og:image"' not in t:
        t = t.replace("</head>", '<meta property="og:image" content="%s">' % url + chr(10) + "</head>", 1)
    if 'name="twitter:image"' not in t:
        t = t.replace("</head>", '<meta name="twitter:image" content="%s">' % url + chr(10) + "</head>", 1)
    if t != s:
        open(path, "w", encoding="utf-8", newline="").write(t)


def main():
    force = "--force" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    os.makedirs(OUT, exist_ok=True)
    pages = sorted(glob.glob(os.path.join(SITE, "analysis-*.html")) + glob.glob(os.path.join(SITE, "course-*.html")))
    done = 0
    for p in pages:
        slug = os.path.splitext(os.path.basename(p))[0]
        if only and only not in slug:
            continue
        png = os.path.join(OUT, slug + ".png")
        if force or not os.path.exists(png):
            e, t, m = info(p)
            render(e, t, m, png)
            done += 1
            print("made", slug)
        point_page(p, slug)
    if not only:
        default = os.path.join(SITE, "og-image.png")
        if force or "--default" in sys.argv:
            render("PGA Tour betting picks", "Bet the course, <em>not the name.</em>",
                   "Free weekly picks, odds analysis and course guides from a strokes gained model.", default)
            print("made default og-image.png")
    print("images generated:", done)


if __name__ == "__main__":
    main()
