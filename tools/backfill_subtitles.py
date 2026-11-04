"""
Adds a SUBTITLE line to the SEO block of every picks article (weekly-model/*/substack_article_*.md) that
lacks one, so older articles match what weekly_model_pipeline.py now generates. Everything in the subtitle
comes from facts already in the article: the event, year, course, the two heaviest model weights and the
value-play odds quoted in the SEO description. Safe to re-run (it skips files that already have a subtitle).
    python tools/backfill_subtitles.py [--dry-run]
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SUFFIXES = (" Country Club", " Golf Club", " Golf Links", " Golf Course", " National Golf Club", " Links")
SG_BARE = {"sg: approach": "Approach", "sg: off the tee": "Off-the-tee", "sg: around the green": "Short-game", "sg: putting": "Putting"}


def short_course(name):
    if " at " in name:
        name = name.split(" at ", 1)[0].strip()
    for suf in SUFFIXES:
        if name.endswith(suf):
            return name[: -len(suf)].strip()
    return name


def phrase(label):
    low = label.lower().strip()
    if low in SG_BARE:
        return SG_BARE[low]
    return re.sub(r"\s+component$", "", label.strip(), flags=re.I)


def build(text):
    title = re.search(r"^ARTICLE TITLE:\s+(.*)$", text, re.M).group(1).strip()
    m = re.match(r"(.+?)\s+(20\d\d)\s+Picks:.*?\bfor\s+(.+)$", title)
    if not m:
        return None
    name, year, course = m.group(1), m.group(2), short_course(m.group(3))
    desc = re.search(r"^SEO DESCRIPTION:\s+(.*)$", text, re.M)
    vm = re.search(r"flags a ([+-]\d+) value play", desc.group(1)) if desc else None
    odds = vm.group(1) if vm else None
    weights = []
    for label, pct in re.findall(r"^- \*\*(.+?) — ([\d.]+)%", text, re.M):
        if not re.search(r"course (history|experience)", label, re.I):
            weights.append((label, float(pct)))
    weights.sort(key=lambda x: -x[1])
    stat = None
    if len(weights) >= 2:
        a, b = weights[0][0], weights[1][0]
        if a.lower() in SG_BARE and b.lower() in SG_BARE:
            stat = "%s and %s play lead the model at %s" % (SG_BARE[a.lower()], SG_BARE[b.lower()].lower(), course)
        else:
            stat = "%s and %s lead the model at %s" % (phrase(a), phrase(b).lower(), course)
    cands = []
    if stat and odds:
        cands += ["%s. Best bets, fades and a %s value play for the %s %s." % (stat, odds, year, name),
                  "%s. Best bets, fades and a %s value play for the %s." % (stat, odds, name),
                  "%s. Best bets, fades and a %s value play." % (stat, odds)]
    if odds:
        cands.append("Model best bets and fades at %s, with a %s value play for the %s." % (course, odds, name))
    cands += ["Model best bets, fades and course-fit stats for the %s %s at %s." % (year, name, course),
              "Model best bets, fades and course-fit stats for the %s." % name]
    for c in cands:
        if 80 <= len(c) <= 160:
            return c
    return None


dry = "--dry-run" in sys.argv
done = skipped = 0
for path in sorted(glob.glob(os.path.join(ROOT, "weekly-model", "*", "substack_article_*.md"))):
    raw = open(path, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    folder = os.path.basename(os.path.dirname(path))
    if "=== SEO METADATA" not in text:
        print("skip (no SEO block):", folder)
        skipped += 1
        continue
    if re.search(r"^SUBTITLE:", text, re.M):
        print("skip (already has a subtitle):", folder)
        skipped += 1
        continue
    sub = build(text)
    if not sub:
        print("skip (could not build a subtitle):", folder)
        skipped += 1
        continue
    new = re.sub(r"^(ARTICLE TITLE:.*)$", lambda m: m.group(1) + "\nSUBTITLE:        %s (%d chars)" % (sub, len(sub)), text, count=1, flags=re.M)
    print("%s: %s" % (folder, sub))
    if not dry:
        open(path, "w", encoding="utf-8", newline="").write(new.replace("\n", "\r\n") if crlf else new)
    done += 1
print("subtitles added: %d, skipped: %d%s" % (done, skipped, " (dry run)" if dry else ""))
