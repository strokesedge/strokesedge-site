"""
Internal linking pass (safe to re-run, idempotent, nothing is ever removed).

  * analysis-*.html and course-*.html get a "Keep reading" block (between <!--RELATED-LINKS--> markers) just
    before the footer: the course guide or analysis page, that event's picks article and recap if they exist,
    the public tracker and two betting guides.
  * the three evergreen guides get the new long-tail guides appended to their "Keep reading" cards
    (between <!--MORE-GUIDES--> markers).
Run it after the weekly page build, publish_picks.py and publish_recaps.py so new pages are linked both ways.
    python tools/add_related_links.py [--dry-run]
"""
import glob
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "Strokes Edge Website HTML")
START, END = "<!--RELATED-LINKS-->", "<!--/RELATED-LINKS-->"
CSS = ("<style>.se-more{margin:2.5rem 0 3rem}.se-more h2{font:700 20px/1.2 'Archivo',sans-serif;margin:0 0 1rem;color:var(--txt)}"
       ".se-more div{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}"
       ".se-more a{display:block;text-decoration:none;background:var(--sur);border:1px solid var(--bdr2);border-radius:4px;padding:16px 18px}"
       ".se-more a:hover{border-color:var(--bdr)}.se-more small{display:block;font:400 10px/1.3 'DM Mono',monospace;letter-spacing:.12em;"
       "text-transform:uppercase;color:var(--g);margin-bottom:6px}.se-more strong{display:block;font:600 16px/1.3 'Outfit',sans-serif;color:var(--txt)}</style>")
GUIDES = [("golf-betting-odds-explained.html", "Golf betting odds explained", "Guide"),
          ("outright-vs-top-10-golf-betting.html", "Outright vs top 10 bets", "Guide"),
          ("each-way-golf-betting-explained.html", "Each-way betting explained", "Guide"),
          ("golf-matchup-bets-explained.html", "Matchup bets explained", "Guide"),
          ("golf-betting-bankroll-management.html", "Bankroll management", "Guide")]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read(p):
    return open(p, encoding="utf-8", newline="").read()


def exists(f):
    return os.path.exists(os.path.join(SITE, f))


def title_of(f):
    m = re.search(r"<title>(.*?)</title>", read(os.path.join(SITE, f)), re.S)
    t = html.unescape(m.group(1)) if m else f
    return re.split(r"\s+[—|\-]\s+|\s+\|\s+", t)[0].strip()


def card(href, label, text):
    return '<a href="%s"><small>%s</small><strong>%s</strong></a>' % (href, html.escape(label), html.escape(text))


def picks_files():
    p = os.path.join(HERE, "picks_articles.json")
    return [r["file"] for r in json.load(open(p, encoding="utf-8"))] if os.path.exists(p) else []


def event_of(analysis):
    m = re.match(r"analysis-(.+)-(20\d\d)\.html$", analysis)
    return (m.group(1), m.group(2)) if m else (None, None)


def block(cards):
    return "%s\n%s<section class=\"se-more\"><h2>Keep reading</h2><div>%s</div></section>\n%s" % (START, CSS, "".join(cards), END)


def put(path, new_block, dry):
    s = read(path)
    crlf = "\r\n" in s
    t = s.replace("\r\n", "\n")
    if START in t:
        t = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda m: new_block, t, flags=re.S)
    else:
        anchor = re.search(r"</div>\s*\n\s*<footer", t)
        if not anchor:
            return False
        t = t[:anchor.start()] + new_block + "\n" + t[anchor.start():]
    if t == s.replace("\r\n", "\n"):
        return False
    if not dry:
        open(path, "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
    return True


def main():
    dry = "--dry-run" in sys.argv
    picks = picks_files()
    analyses = [os.path.basename(p) for p in glob.glob(os.path.join(SITE, "analysis-*.html"))]
    course_to_analysis = {}
    for a in analyses:
        m = re.search(r'href="(course-[a-z0-9\-]+\.html)"', read(os.path.join(SITE, a)))
        if m:
            course_to_analysis.setdefault(m.group(1), a)
    changed = 0
    for a in sorted(analyses):
        if a == "analysis.html":
            continue
        ev, yr = event_of(a)
        cards = []
        m = re.search(r'href="(course-[a-z0-9\-]+\.html)"', read(os.path.join(SITE, a)))
        if m and exists(m.group(1)):
            cards.append(card(m.group(1), "Course guide", "What the course rewards"))
        pk = next((f for f in picks if ev and f.startswith(ev + "-" + (yr or ""))), None)
        if pk and exists(pk + ".html"):
            cards.append(card(pk + ".html", "Weekly picks", "Best bets and fades for this event"))
        rc = "%s-%s-recap-results.html" % (ev, yr)
        if exists(rc):
            cards.append(card(rc, "Recap", "How the picks finished"))
        cards.append(card("picks.html", "Pick tracker", "Every settled bet, wins and losses"))
        cards += [card(GUIDES[0][0], "Guide", GUIDES[0][1]), card(GUIDES[1][0], "Guide", GUIDES[1][1])]
        changed += put(os.path.join(SITE, a), block(cards[:6]), dry)
    for c in sorted(glob.glob(os.path.join(SITE, "course-*.html"))):
        cf = os.path.basename(c)
        cards = []
        an = course_to_analysis.get(cf)
        if an:
            cards.append(card(an, "Event analysis", "Key stats and top course fits"))
            ev, yr = event_of(an)
            pk = next((f for f in picks if f.startswith(ev + "-" + (yr or ""))), None)
            if pk and exists(pk + ".html"):
                cards.append(card(pk + ".html", "Weekly picks", "Best bets and fades for this event"))
            rc = "%s-%s-recap-results.html" % (ev, yr)
            if exists(rc):
                cards.append(card(rc, "Recap", "How the picks finished"))
        cards.append(card("pga-tour-betting-guide.html", "Guide", "PGA Tour betting guide"))
        cards.append(card(GUIDES[2][0], "Guide", GUIDES[2][1]))
        cards.append(card(GUIDES[3][0], "Guide", GUIDES[3][1]))
        changed += put(c, block(cards[:6]), dry)
    # evergreen guides
    more = "".join('<a href="%s">%s<small>%s</small></a>' % (h, html.escape(t), "Betting guide") for h, t, _ in GUIDES)
    mblock = "<!--MORE-GUIDES-->%s<!--/MORE-GUIDES-->" % more
    for g in ("pga-tour-betting-guide.html", "how-to-bet-on-golf.html", "strokes-gained-explained.html"):
        p = os.path.join(SITE, g)
        s = read(p)
        if "<!--MORE-GUIDES-->" in s:
            t = re.sub(r"<!--MORE-GUIDES-->.*?<!--/MORE-GUIDES-->", lambda m: mblock, s, flags=re.S)
        else:
            m = re.search(r'(<div class="related">.*?)(</div>\s*</main>)', s, re.S)
            if not m:
                print("no related block in", g)
                continue
            t = s[:m.end(1)] + mblock + s[m.end(1):]
        if t != s:
            changed += 1
            if not dry:
                open(p, "w", encoding="utf-8", newline="").write(t)
    print("%s %d pages" % ("would change" if dry else "changed", changed))


if __name__ == "__main__":
    main()
