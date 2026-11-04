"""
Release a PAST event's model workbook as a free sample (lead magnet for the $7 workbook and the membership).

    python tools/release_sample_workbook.py vidantaworld-mexico-open --confirm-data-golf-ok [--dry-run]

What it does, for a finished event only (its recap must already be on Substack):
  * copies weekly-model/<event>/StrokesEdge_*_MODEL.xlsx to Strokes Edge Website HTML/downloads/
    strokesedge-sample-workbook.xlsx (one sample at a time, the new one replaces the old; /downloads/* is noindex)
  * builds free-sample-workbook.html (what is inside, the event it covers, link to that recap, signup and the
    $7 / membership links) and adds it to the sitemap
  * prints the exact git commands. The repo ignores *.xlsx on purpose, so the one released file needs `git add -f`.

SAFETY: the repo is public and the workbook holds Data Golf derived data. The tool refuses to run without
--confirm-data-golf-ok, which means "I checked Data Golf's terms and redistribution of a past event's workbook is allowed".
Never release the current week's workbook, it is the paid product.
"""
import argparse
import glob
import json
import os
import shutil
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sitepage import render_page, SITE, esc  # noqa: E402
from publish_picks import add_to_sitemap, feed_items  # noqa: E402

ROOT = os.path.dirname(HERE)
WEEKLY = os.path.join(ROOT, "weekly-model")
DEST = os.path.join(SITE, "downloads", "strokesedge-sample-workbook.xlsx")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CSS = ".art h3{font:700 18px/1.3 'Archivo',sans-serif;font-stretch:104%;margin:1.4rem 0 .35rem;color:var(--txt)}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("event")
    ap.add_argument("--confirm-data-golf-ok", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.confirm_data_golf_ok:
        raise SystemExit("Refusing: confirm Data Golf's terms allow sharing a past event's workbook, then add --confirm-data-golf-ok")
    d = os.path.join(WEEKLY, a.event)
    xl = sorted(glob.glob(os.path.join(d, "StrokesEdge_*_MODEL.xlsx")))
    if not xl:
        raise SystemExit("no StrokesEdge_*_MODEL.xlsx in " + d)
    st = json.load(open(os.path.join(d, "state.json"), encoding="utf-8"))
    name = st["event_name"]
    year = st["start_date"][:4]
    recap = [t for t, _ in feed_items() if t.lower().startswith(name.lower() + " " + year) and any(w in t.lower() for w in ("recap", "results"))]
    if not recap:
        raise SystemExit("Refusing: no recap for %s on the Substack feed yet. Only release a finished event." % name)
    slug = "%s-%s-recap-results" % (st["slug"], year)
    pages = []
    body = ('<div class="art"><p>This is the real model workbook from the <strong>%s %s</strong>, released free now that the event is over. '
            'It is the same seven-sheet file members get every week, so you can see exactly what the model scores, how it ranks the whole field and where the picks came from.</p>'
            '<p><a class="btn" href="downloads/strokesedge-sample-workbook.xlsx">Download the free sample workbook (.xlsx) &rarr;</a></p>'
            '<h2>What is inside</h2><ul>'
            '<li><strong>Cover.</strong> The top picks, fades and matchups, with a glossary of every stat.</li>'
            '<li><strong>Dashboard.</strong> The top players by model score.</li>'
            '<li><strong>Picks Card.</strong> Every pick tier with odds, model rank, edge and the reasoning.</li>'
            '<li><strong>Value Screen.</strong> Players who clear the thresholds, sorted by the gap to the market price.</li>'
            '<li><strong>Model Rankings.</strong> The full field with every input to the score.</li>'
            '<li><strong>Watch List.</strong> Players outside the regression and why.</li>'
            '<li><strong>Model Weights.</strong> The weight on each stat for that course.</li></ul>'
            '<h2>How to use it</h2><p>Open the Picks Card first, then read how those picks finished in the '
            '<a href="%s.html">%s %s recap</a>. The results are in the <a href="picks.html">public pick tracker</a>, wins and losses together. '
            'The current week\'s workbook is $7, or included with a <a href="membership.html">membership</a>.</p>'
            '<p><em>For research and entertainment, not financial advice. Gamble responsibly.</em></p></div>') % (esc(name), year, slug, esc(name), year)
    title = "Free Golf Betting Model Workbook (Excel Sample)"
    desc = ("Download a free StrokesEdge model workbook from the %s %s: full-field strokes gained rankings, picks card and value screen, as an Excel file." % (name, year))
    desc = desc if 110 <= len(desc) <= 160 else desc[:156].rsplit(" ", 1)[0] + "..."
    if a.dry_run:
        print("dry run OK:", xl[-1], "->", DEST, "|", title, len(desc))
        return
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    shutil.copyfile(xl[-1], DEST)
    render_page("free-sample-workbook.html", title, desc, "Free sample model <span>workbook.</span>",
                "A real StrokesEdge workbook from a finished tournament, free to download so you can see what the model does before you buy.",
                body, "Free download", extra_css=CSS, schema="WebPage")
    add_to_sitemap("free-sample-workbook", datetime.now().strftime("%Y-%m-%d"), "0.8", "monthly")
    print("released the %s %s workbook. Review the page, then:" % (name, year))
    print('  git add -f "Strokes Edge Website HTML/downloads/strokesedge-sample-workbook.xlsx" "Strokes Edge Website HTML/free-sample-workbook.html" "Strokes Edge Website HTML/sitemap.xml" tools/release_sample_workbook.py')
    print("Then link it: the homepage Newsletter section, the membership page and the Substack welcome email.")


if __name__ == "__main__":
    main()
