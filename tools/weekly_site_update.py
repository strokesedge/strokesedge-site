"""
One command for the weekly site update, so nothing is done by hand twice.

  python tools/weekly_site_update.py prepare <weekly-model folder> [--dry-run] [--hashtag "#Tag"]
      Run after the analysis page and course guide exist (the existing weekly update builds those).
      Reads the analysis page and updates:
        * homepage: the "This week" block, the hero callouts and date line, the "Read next" featured card
        * tweet config (strokesedge-twitter/shared/tournament_config.py): event, course stats, top weights
        * picks.html: adds this week's access code to validCodes (read from the picks article)
        * social images, canonical and nav fixes, signup wiring (all idempotent)
      It never commits or pushes. Review with git diff, then commit.

  python tools/weekly_site_update.py publish <weekly-model folder>
      Run AFTER the Substack post is live. Publishes the picks article page on strokesedge.com
      (refuses if it is not on the Substack feed) and rebuilds the archive and social image.
      Then refreshes the analysis page to the article (refresh_analysis_page.py --posted), adds related
      links and runs the audit.

  python tools/weekly_site_update.py recaps <weekly-model folder>
      Run AFTER the Monday recap is on Substack. Publishes every new recap on the site (publish_recaps.py),
      rebuilds weekly-recaps.html, links the pages and runs the audit.

Example: python tools/weekly_site_update.py prepare world-wide-technology-championship
"""
import argparse
import glob
import html
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, "Strokes Edge Website HTML")
TWEET_CFG = os.path.join(ROOT, "strokesedge-twitter", "shared", "tournament_config.py")
sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"


def clean(x):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(x))).strip()


def esc(x):
    return html.escape(x, quote=True)


# ----------------------------------------------------------------------------- read the analysis page
def read_facts(analysis_path):
    s = open(analysis_path, encoding="utf-8").read()
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    if not h1:
        raise SystemExit("no <h1> in " + analysis_path)
    name = clean(h1.group(1)).rstrip(". ")
    name = re.sub(r"\s+20\d\d$", "", name)
    meta = re.search(r'<div class="[^"]*hero-meta[^"]*"[^>]*>(.*?)</div>', s, re.S)
    if not meta:
        raise SystemExit("no hero-meta line in " + analysis_path)
    parts = [p.strip() for p in clean(meta.group(1)).split("·")]
    course = parts[0]
    par = yards = dates = None
    for p in parts[1:]:
        m = re.search(r"\bPar (\d+)", p)
        if m:
            par = int(m.group(1))
        m = re.search(r"([\d,]+)\s*(?:tournament )?yards", p)
        if m:
            yards = m.group(1)
        if re.search(r"\b(%s)\b" % MONTHS, p) and re.search(r"\d{4}", p):
            dates = p
    eyebrow = re.search(r'<div class="(?:hero-eyebrow|hero-tag|eyebrow|hero-loc)[^"]*"[^>]*>(.*?)</div>', s, re.S)
    location = None
    if eyebrow:
        ep = [x.strip() for x in clean(eyebrow.group(1)).split("·")]
        if len(ep) > 1:
            location = ep[-1]
    starts = [m.start() for m in re.finditer(r'<div class="w-row"', s)]
    weights = []
    for k, st in enumerate(starts):
        seg = s[st:(starts[k + 1] if k + 1 < len(starts) else st + 900)]
        lab = re.search(r'class="w-label">(.*?)</div>', seg, re.S)
        pct = re.search(r'class="w-pct">\s*(\d+)\s*%', seg)
        if lab and pct and int(pct.group(1)) > 0:
            weights.append((clean(lab.group(1)), int(pct.group(1))))
    if not (par and yards and dates and weights):
        raise SystemExit("could not read par/yardage/dates/weights from %s (par=%s yards=%s dates=%s weights=%d)"
                         % (analysis_path, par, yards, dates, len(weights)))
    cm = re.search(r'href="(course-[a-z0-9\-]+\.html)"', s)
    designer = None
    dm = re.search(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)+) (?:design\b|designed\b)", clean(s))
    if dm:
        designer = dm.group(1)
    # "Nov 5-8, 2026" or "Oct 29 to Nov 1, 2026" or "Oct 29-Nov 1"
    dm = re.search(r"(%s) (\d{1,2})\s*(?:[–\-]|to)\s*(?:(%s) )?(\d{1,2})" % (MONTHS, MONTHS), dates)
    if not dm:
        raise SystemExit("could not parse the dates: " + dates)
    m1, d1, m2, d2 = dm.group(1), dm.group(2), dm.group(3), dm.group(4)
    span = "%s %s to %s%s" % (m1, d1, (m2 + " ") if m2 else "", d2)
    year = re.search(r"(20\d\d)", dates).group(1)
    return {"name": name, "course": course, "par": par, "yards": yards, "dates": dates, "span": span,
            "round1": "%s %s" % (m1, d1), "location": location, "weights": weights, "course_file": cm.group(1) if cm else None,
            "designer": designer, "year": int(year), "analysis_file": os.path.basename(analysis_path)}


def default_hashtag(name):
    words = name.replace("&", "and").split()
    camel = "".join(re.sub(r"[^A-Za-z0-9]", "", w) for w in words)
    if len(camel) <= 22:
        return "#" + camel
    return "#" + "".join(w[0].upper() for w in words[:-1]) + re.sub(r"[^A-Za-z0-9]", "", words[-1])


# ----------------------------------------------------------------------------- homepage
BLOCKS = {
    "callouts": (r'(      <div class="call c1">.*?<div class="call c3">.*?</div>)', "callouts"),
    "desk": (r'(<section class="desk" id="desk">.*?</section>)', "desk"),
    "feat": (r'(<a class="feat" href="[^"]*">.*?</a>)', "feat"),
}


def wrap_markers(s):
    for key, (pat, tag) in BLOCKS.items():
        if "<!--WEEK:%s-->" % tag in s:
            continue
        m = re.search(pat, s, re.S)
        if not m:
            raise SystemExit("homepage block not found: " + key)
        s = s[:m.start()] + "<!--WEEK:%s-->" % tag + m.group(1) + "<!--/WEEK:%s-->" % tag + s[m.end():]
    if "<!--WEEK:src-->" not in s:
        m = re.search(r'<div class="src"><span>(.*?)</span>', s, re.S)
        if not m:
            raise SystemExit("homepage block not found: src")
        s = s[:m.start(1)] + "<!--WEEK:src-->" + m.group(1) + "<!--/WEEK:src-->" + s[m.end(1):]
    return s


def swap(s, tag, new):
    pat = re.compile(r"<!--WEEK:%s-->.*?<!--/WEEK:%s-->" % (tag, tag), re.S)
    if not pat.search(s):
        raise SystemExit("marker missing: " + tag)
    return pat.sub(lambda m: "<!--WEEK:%s-->%s<!--/WEEK:%s-->" % (tag, new, tag), s, count=1)


def render_home(s, f):
    w = f["weights"]
    top = max(p for _, p in w)
    top5 = sorted(w, key=lambda x: -x[1])[:5]
    short = f["course"].split(" at ")[0]
    name_words = f["name"].split()
    h2 = esc(" ".join(name_words[:-1])) + " <em>" + esc(name_words[-1]) + "</em>" if len(name_words) > 1 else esc(f["name"])
    venue = f["course"] + (", " + f["location"].split(", ", 1)[-1] if False else "")
    where = esc(f["course"]) + (", " + esc(f["location"]) if f["location"] and f["location"] not in f["course"] else "")
    intro = "%s. The model puts the most weight on %s (%d%%) and %s (%d%%) this week." % (
        where, esc(top5[0][0]), top5[0][1], esc(top5[1][0]), top5[1][1])
    gauges = "\n".join('        <div class="gauge"><span>%s</span><b>%d%%</b><div class="ticks"><i style="--w:%d%%"></i></div></div>'
                       % (esc(l), p, round(p / top * 100)) for l, p in top5)
    callouts = ('      <div class="call c1"><b>%d%%</b>%s</div>\n      <div class="call c2"><b>%d%%</b>%s</div>\n'
                '      <div class="call c3"><b>%s</b>Yards · Par %d</div>'
                % (top5[0][1], esc(top5[0][0]), top5[1][1], esc(top5[1][0]), f["yards"], f["par"]))
    course_link = ""
    if f["course_file"]:
        course_link = ('\n      <a class="cell go b-c" href="%s"><div><small>Course guide</small><strong>%s betting guide</strong></div>'
                       '<span class="arrow">↗</span></a>' % (f["course_file"], esc(f["course"])))
    desk = ('<section class="desk" id="desk">\n  <div class="wrap">\n    <div class="desk-h">\n'
            '      <div><div class="eb">This week</div><h2>%s</h2></div>\n      <p>%s</p>\n    </div>\n'
            '    <div class="bento">\n      <div class="cell b-w arm" id="weights">\n        <h3>How the model weights this course</h3>\n%s\n      </div>\n'
            '      <div class="cell b-f"><h3>The course</h3><div class="facts"><div class="fact"><b>%d</b><span>Par</span></div>'
            '<div class="fact"><b>%s</b><span>Yards</span></div><div class="fact"><b>%s</b><span>Round 1</span></div></div></div>\n'
            '      <a class="cell go b-a" href="%s"><div><small>Free</small><strong>Read the full analysis</strong></div><span class="arrow">↗</span></a>%s\n'
            '    </div>\n  </div>\n</section>' % (h2, intro, gauges, f["par"], f["yards"], f["round1"], f["analysis_file"], course_link))
    feat = ('<a class="feat" href="%s"><div><small>This week · %s</small><strong>%s picks and analysis</strong></div>'
            '<span class="arrow">↗</span></a>' % (f["analysis_file"], esc(f["span"]), esc(f["name"])))
    s = wrap_markers(s)
    s = swap(s, "callouts", callouts)
    s = swap(s, "desk", desk)
    s = swap(s, "feat", feat)
    s = swap(s, "src", esc(short) + " · " + esc(f["span"]))
    return s


# ----------------------------------------------------------------------------- tweet config
def update_tweet_config(f, hashtag):
    s = open(TWEET_CFG, encoding="utf-8", newline="").read()
    top5 = sorted(f["weights"], key=lambda x: -x[1])[:5]
    tournament = ('TOURNAMENT = {\n    "name": "%s",\n    "year": %d,\n    "course_file": "%s",\n    "analysis_file": "%s",\n'
                  '    "methodology_file": "methodology.html",\n    "hashtag": "%s",\n}\n'
                  % (f["name"], f["year"], f["course_file"] or "", f["analysis_file"], hashtag))
    stats = 'COURSE_STATS = {\n    "par": %d,\n    "yardage": %s,\n' % (f["par"], f["yards"].replace(",", ""))
    if f["location"]:
        stats += '    "location": "%s",\n' % f["location"]
    if f["designer"]:
        stats += '    "designer": "%s",\n' % f["designer"]
    stats += "}\n"
    weights = "MODEL_WEIGHTS = [\n" + "".join('    ("%s", %d),\n' % (l, p) for l, p in top5) + "]\n"
    crlf = "\r\n" in s
    t = s.replace("\r\n", "\n")
    for pat, new in ((r"TOURNAMENT = \{.*?\n\}\n", tournament), (r"COURSE_STATS = \{.*?\n\}\n", stats), (r"MODEL_WEIGHTS = \[.*?\n\]\n", weights)):
        if not re.search(pat, t, re.S):
            raise SystemExit("tournament_config.py block not found: " + pat[:20])
        t = re.sub(pat, lambda m: new, t, count=1, flags=re.S)
    return t.replace("\n", "\r\n") if crlf else t


# ----------------------------------------------------------------------------- access code
def add_access_code(event_dir):
    arts = sorted(glob.glob(os.path.join(event_dir, "substack_article_*.md")))
    if not arts:
        return None, "no picks article found, so no access code was added"
    raw = open(arts[-1], encoding="utf-8").read()
    m = re.search(r"access code this week:\s*(\S+)", raw)
    if not m:
        return None, "the picks article has no access code line"
    code = m.group(1).strip()
    p = os.path.join(SITE, "picks.html")
    s = open(p, encoding="utf-8", newline="").read()
    arr = re.search(r"var validCodes=\[(.*?)\];", s, re.S)
    if not arr:
        return None, "validCodes array not found in picks.html"
    if "'%s'" % code in arr.group(1):
        return code, "already in picks.html"
    new = "var validCodes=[%s,'%s'];" % (arr.group(1), code)
    return code, (s[:arr.start()] + new + s[arr.end():])


# ----------------------------------------------------------------------------- main
def run(cmd):
    r = subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True, text=True)
    return (r.stdout.strip().splitlines() or [""])[-1]


def prepare(a):
    event_dir = os.path.join(ROOT, "weekly-model", a.event)
    analysis = os.path.join(SITE, "analysis-%s-%s.html" % (a.event, a.year))
    if a.analysis:
        analysis = os.path.join(SITE, a.analysis)
    if not os.path.exists(analysis):
        raise SystemExit("analysis page not found: %s (run the weekly page build first, or pass --analysis)" % analysis)
    f = read_facts(analysis)
    hashtag = a.hashtag or default_hashtag(f["name"])
    print("Event      :", f["name"], "|", f["course"], "| par", f["par"], "|", f["yards"], "yd |", f["dates"])
    print("Top weights:", ", ".join("%s %d%%" % (l, p) for l, p in sorted(f["weights"], key=lambda x: -x[1])[:5]))
    print("Hashtag    :", hashtag, "| course guide:", f["course_file"])

    home_p = os.path.join(SITE, "index.html")
    home = open(home_p, encoding="utf-8", newline="").read()
    new_home = render_home(home, f)
    new_cfg = update_tweet_config(f, hashtag)
    code, picks_new = add_access_code(event_dir)

    if a.dry_run:
        print("\n[dry run] homepage would change:", new_home != home, "| tweet config would change:", new_cfg != open(TWEET_CFG, encoding="utf-8", newline="").read())
        print("[dry run] access code:", code, "->", picks_new if picks_new.startswith("already") or not picks_new.startswith("<") and len(picks_new) < 90 else "would be added to picks.html")
        return
    open(home_p, "w", encoding="utf-8", newline="").write(new_home)
    open(TWEET_CFG, "w", encoding="utf-8", newline="").write(new_cfg)
    print("\nWrote: homepage This-week block, hero callouts, date line and Read-next card; tweet config.")
    if code and not picks_new.startswith("already") and len(picks_new) > 200:
        open(os.path.join(SITE, "picks.html"), "w", encoding="utf-8", newline="").write(picks_new)
        print("Added access code", code, "to picks.html")
    else:
        print("Access code:", code, "-", picks_new if code is None or len(picks_new) < 200 else "")
    for label, cmd in (("social images", ["tools/make_og_images.py"]), ("canonicals and nav", ["tools/site_fixes_2026_11_03.py"]),
                       ("analysis gate", ["tools/site_updates_2026_11_04.py"]), ("related links", ["tools/add_related_links.py"]), ("signup wiring", ["tools/add_signup.py"])):
        print("%-20s %s" % (label + ":", run(cmd)))
    audit = subprocess.run([sys.executable, os.path.join(HERE, "audit_site.py")], cwd=ROOT, capture_output=True, text=True)
    print("%-20s %s" % ("site audit:", audit.stdout.strip().replace("\n", "\n" + " " * 21)))
    # heads-up about picks visible on the analysis page before the newsletter goes out
    try:
        from publish_picks import feed_items, find_on_substack, parse_article
        arts = sorted(glob.glob(os.path.join(event_dir, "substack_article_*.md")))
        if arts:
            seo, _, _ = parse_article(arts[-1])
            live = find_on_substack(seo.get("ARTICLE TITLE", ""), feed_items())
            page = open(analysis, encoding="utf-8").read()
            if not live and "id=\"cliff-content\"" in page and "Full Picks Card" in page:
                print("\nWARNING: the full picks card is in the analysis page source (only blurred) and the Substack post is not live yet.")
                print("         Anyone can read it with view-source before your newsletter goes out.")
    except Exception as e:
        print("(could not check the Substack feed:", e, ")")
    print("\nNext: review `git diff --stat`, open the homepage, then commit. After you post on Substack run:")
    print("      python tools/weekly_site_update.py publish", a.event)


def finish_checks():
    """Link the new pages both ways, wire signup, then audit."""
    for label, cmd in (("related links", ["tools/add_related_links.py"]), ("signup wiring", ["tools/add_signup.py"])):
        print("%-20s %s" % (label + ":", run(cmd)))
    audit = subprocess.run([sys.executable, os.path.join(HERE, "audit_site.py")], cwd=ROOT, capture_output=True, text=True)
    print("%-20s %s" % ("site audit:", audit.stdout.strip().replace("\n", "\n" + " " * 21)))


def publish(a):
    """After the Substack picks post is live: picks page on the site, analysis page matched to the article, links, audit."""
    r = subprocess.run([sys.executable, os.path.join(HERE, "publish_picks.py"), a.event], cwd=ROOT)
    if r.returncode != 0:
        return
    page = os.path.join(SITE, "analysis-%s-%s.html" % (a.event, a.year))
    if os.path.exists(page):
        print("\nRefreshing the analysis page to match the article (needs DATAGOLF_API_KEY, skip with Ctrl+C if absent)")
        subprocess.run([sys.executable, os.path.join(HERE, "refresh_analysis_page.py"), a.event, "--year", a.year, "--posted"], cwd=ROOT)
    finish_checks()
    print("\nNext: review, then commit the picks page, the analysis page, weekly-picks.html, sitemap.xml, og/ images and tools/picks_articles.json.")


def recaps(a):
    """After the Monday recap is on Substack: publish it (and any other new recap) on the site."""
    subprocess.run([sys.executable, os.path.join(HERE, "publish_recaps.py")], cwd=ROOT)
    finish_checks()
    print("\nNext: review, then commit the recap page(s), weekly-recaps.html, sitemap.xml, og/ images and tools/recaps.json.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["prepare", "publish", "recaps"])
    ap.add_argument("event", help="folder name under weekly-model/, for example world-wide-technology-championship")
    ap.add_argument("--year", default="2026")
    ap.add_argument("--analysis", help="analysis page file name if it does not follow analysis-<event>-<year>.html")
    ap.add_argument("--hashtag")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    {"prepare": prepare, "publish": publish, "recaps": recaps}[args.command](args)
