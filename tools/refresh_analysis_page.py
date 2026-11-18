"""
Refresh the picks-dependent parts of an event's analysis page from the model's own data and LIVE odds, so the
page always matches the article. Use it after re-running the model (for example Wednesday, when odds and the
field have moved).

    python tools/refresh_analysis_page.py <weekly-model folder> [--posted] [--dry-run]

Updates (the same tier selections the Substack article uses, from weekly-model/<event>/state.json plus current odds):
  * section 02: how many players were scored and how many cleared the Winner DNA gates
  * section 03: top 3 course fits (stat profile only, no odds)
  * section 04: the featured pick (largest positive win edge among the model's top five)
  * section 06: the full picks card (tiers, odds, why), its intro and footnote
  * the FAQ answer "Who is favored", both the visible text and the page's FAQ structured data
For events on or after 2027-01-21 (paid launch) the picks card is removed from the page entirely, not refreshed.
--posted switches "publish before Thursday" wording to "now in the newsletter" once the Substack post is live.
Needs DATAGOLF_API_KEY (live odds). It edits only the analysis page, never commits or pushes.
"""
import argparse
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, "Strokes Edge Website HTML")
WEEKLY = os.path.join(ROOT, "weekly-model")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SHORT = {"sg_app_blend": "App", "sg_ott_blend": "OTT", "sg_putt_blend": "Putt", "sg_arg_blend": "ARG",
         "cf_approach_comp": "Course-Fit App", "cf_short_comp": "Course-Fit Short Game",
         "driving_distance_adjustment": "Distance", "driving_accuracy_adjustment": "Accuracy"}


def esc(x):
    return html.escape(str(x), quote=False)


_MD = {}


def fin(p, d):
    """Finish-market prices from the same Data Golf board the workbook uses. A finish-market row never shows the
    outright price (2026-11-17 standard)."""
    t10 = p._fmt_odds(p._odds_index(_MD, "outrights_top_10").get(d))
    t20 = p._fmt_odds(p._odds_index(_MD, "outrights_top_20").get(d))
    return "Top 10 %s, Top 20 %s" % (t10, t20)


def load(slug):
    sys.path.insert(0, WEEKLY)
    os.chdir(WEEKLY)
    import weekly_model_pipeline as p
    ev = next((e for e in p.detect_events_this_week() if e["slug"] == slug), None)
    if not ev:
        raise SystemExit("event %s is not in this week's Data Golf schedule" % slug)
    st = p.load_state(ev)
    if "metrics" not in st:
        raise SystemExit("state.json has no model results for %s yet" % slug)
    metrics, l1, l2 = p._int_keyed(st["metrics"]), p._int_keyed(st["l1_results"]), p._int_keyed(st["l2_results"])
    md = p.check_markets(ev["tour"])
    global _MD
    _MD = md
    if not md["outrights_ready"]:
        raise SystemExit("outright odds are not live, cannot refresh")
    l3 = p.compute_l3(l1, md)
    tiers = p.assign_pick_tiers(l2, l3, md)
    pin_to_article(p, ev, metrics, l3)
    return p, ev, metrics, l1, l2, l3, tiers


def pin_to_article(p, ev, metrics, l3):
    r"""Odds drift after the article is written. Use the article's own odds, L1 score and win edge per player so
    the page and the article agree. Players not listed in the article keep live values."""
    import glob
    files = glob.glob(os.path.join(WEEKLY, ev["slug"], "substack_article_*.md"))
    if not files:
        return
    text = open(files[0], encoding="utf-8").read()
    rx = re.compile(r"([A-Z][^,()*]+, [^()*]+?) \(([+-]\d{3,5})\)")
    byname = {metrics[d]["player_name"]: d for d in l3 if d in metrics}
    seen, hit = set(), 0
    for line in text.splitlines():
        m = rx.search(line)
        if not m:
            continue
        d = byname.get(m.group(1).strip().lstrip("-").strip())
        if d is None:
            continue
        if d not in seen:
            l3[d]["win_odds"] = float(m.group(2))
            seen.add(d)
            hit += 1
        e = re.search(r"([+-]\d+\.\d+)% (?:edge|outright edge)|WIN EDGE ([+-]\d+\.\d+)%", line)
        if e:
            l3[d]["win_edge_pct"] = float(e.group(1) or e.group(2))
    print("pinned %d players to the article's odds and edges" % hit)


def build(p, ev, metrics, l1, l2, l3, tiers, posted):
    name = lambda d: p._player_first_last(metrics[d]["player_name"])
    fmt = lambda d: ("%+.0f" % float(l3[d]["win_odds"])) if l3[d].get("win_odds") not in (None, "") else "n/a"
    passers = sorted((d for d, r in l2.items() if r["pass"] and d in l3), key=lambda d: l3[d]["l1_score"], reverse=True)
    rank = {d: i + 1 for i, d in enumerate(passers)}

    # Components that are identical for every player carry no signal (for example the course-fit columns at a
    # venue the Tour has never played), so they must never be cited as a strength.
    _vals = {}
    for _d in l1:
        for _k, _v in l1[_d]["components"].items():
            _vals.setdefault(_k, set()).add(round(float(_v["value"]), 9))
    dead = {k for k, v in _vals.items() if len(v) <= 1}

    def comps(d, n=2, by="weight"):
        c = {k: v for k, v in l1[d]["components"].items() if k not in dead}
        if by == "percentile":
            top = sorted(sorted(c.items(), key=lambda kv: -kv[1]["weight_pct"])[:3], key=lambda kv: -kv[1]["percentile"])[:n]
        else:
            top = sorted(c.items(), key=lambda kv: -kv[1]["weight_pct"])[:n]
        return top

    def long_bits(d, n=2):
        return ", ".join("%s %s (%s percentile)" % (p.FACTOR_CATALOG.get(k, k).split(" (")[0], p._fmt_factor_value(v["value"]),
                                                    p._ordinal(v["percentile"])) for k, v in comps(d, n))

    def profile(d):
        return ", ".join("%s pctile %s" % (p._ordinal(v["percentile"]), SHORT.get(k, k)) for k, v in comps(d, 2, "percentile"))

    n_scored, n_pass = len(l2), sum(1 for r in l2.values() if r["pass"])

    # --- section 03: top 3 fits
    rows03 = []
    for d in passers[:3]:
        rows03.append('      <tr><td style="color:var(--txt);font-weight:500">%s</td><td class="cg">%s</td><td>Model rank #%d, L1 %.1f. %s</td></tr>'
                      % (esc(name(d)), esc(profile(d)), rank[d], l3[d]["l1_score"], esc(long_bits(d, 2))))

    # --- section 04: featured pick = largest positive win edge among the top five
    top5 = passers[:5]
    pos = [d for d in top5 if (l3[d]["win_edge_pct"] or 0) > 0]
    feat = max(pos, key=lambda d: l3[d]["win_edge_pct"]) if pos else passers[0]
    feat_text = ("The model's largest positive win edge among its top five, built on %s. " % long_bits(feat, 2).lower().replace("percentile", "percentile")
                 if pos else "The model's top-ranked player this week, built on %s. " % long_bits(feat, 2))

    # --- section 06: picks card
    best_edge = max((l3[d]["win_edge_pct"] or -99 for d in tiers["ew_winner"] + tiers["longshot_value"]), default=None)
    card = []

    def row(tag_cls, tag, bet, odds, why):
        card.append('          <tr>\n            <td><span class="%s">%s</span></td>\n            <td style="color:var(--txt);font-weight:500">%s</td>\n'
                    '            <td class="cg">%s</td>\n            <td>%s</td>\n          </tr>' % (tag_cls, tag, esc(bet), odds, esc(why)))

    for d in tiers["ew_winner"]:
        e = l3[d]["win_edge_pct"]
        why = "Model rank #%d, L1 %.1f. %s, %+.2f%% win edge%s" % (rank[d], l3[d]["l1_score"], long_bits(d, 2), e,
                                                                  ", the best on the card" if e == best_edge else "")
        row("tag-pass", "E/W WINNER", name(d), fmt(d), why)
    for d in tiers["longshot_value"]:
        e = l3[d]["win_edge_pct"]
        row("tag-soft", "LONGSHOT / VALUE", name(d), fmt(d),
            "Model rank #%d, L1 %.1f. %s, %+.2f%% win edge at a long price" % (rank[d], l3[d]["l1_score"], long_bits(d, 2), e))
    for d in tiers["top10_top20"]:
        e = l3[d]["win_edge_pct"]
        tail = ("%+.2f%% outright edge, so finish markets only" % e) if (e is not None and e < 0) else ("%+.2f%% win edge" % e)
        row("tag-soft", "TOP 10 / TOP 20", name(d), fin(p, d), "Model rank #%d, L1 %.1f. %s, %s" % (rank[d], l3[d]["l1_score"], long_bits(d, 2), tail))
    for m in tiers["matchup"]:
        a, b = m["favor"], m["against"]
        row("tag-soft", "MATCHUP", "%s over %s" % (name(a), name(b)), "—",
            "Model favors %s (L1 %.1f) over %s (L1 %.1f) despite the market pricing it the other way" % (
                p._player_last_name(metrics[a]["player_name"]) if hasattr(p, "_player_last_name") else name(a).split()[-1], l3[a]["l1_score"],
                name(b).split()[-1], l3[b]["l1_score"]))
    for d in tiers["fade"]:
        row("tag-fail", "FADE", name(d), fmt(d), "%+.2f%% win edge. Fade outright winner only. The finish markets remain viable (%s)." % (l3[d]["win_edge_pct"], fin(p, d)))

    fav = min((d for d in l3 if l3[d].get("win_odds") not in (None, "")), key=lambda d: float(l3[d]["win_odds"]))
    intro06 = ("Full StrokesEdge model workbook output, live Data Golf field, skill ratings, and sportsbook odds. %s is the betting favorite at %s, "
               "and the model finds its value further down the board, with %s the clearest positive-edge outright play among the top-ranked players."
               % (name(fav), fmt(fav), name(feat)))
    faq = ("%s is the betting favorite at %s. The StrokesEdge model's top-ranked player is %s (%s, L1 %.1f)%s%s" % (
        name(fav), fmt(fav), name(passers[0]), fmt(passers[0]), l3[passers[0]]["l1_score"],
        (", and its largest positive win edge among the top five belongs to %s (%s, %+.2f%%)." % (name(feat), fmt(feat), l3[feat]["win_edge_pct"])) if pos else ".",
        (" The model fades %s outright." % name(tiers["fade"][0])) if tiers["fade"] else ""))
    return {"n_scored": n_scored, "n_pass": n_pass, "rows03": "\n".join(rows03), "feat_name": name(feat), "feat_text": feat_text,
            "card": "\n".join(card), "intro06": intro06, "faq": faq, "summary": {
                "favorite": "%s %s" % (name(fav), fmt(fav)), "top_ranked": name(passers[0]), "featured": name(feat),
                "ew": [name(d) + " " + fmt(d) for d in tiers["ew_winner"]], "longshot": [name(d) + " " + fmt(d) for d in tiers["longshot_value"]],
                "top10_20": [name(d) + " " + fmt(d) for d in tiers["top10_top20"]], "fade": [name(d) + " " + fmt(d) for d in tiers["fade"]],
                "matchups": len(tiers["matchup"])}}


# Paid launch (2026-11-16): for events on or after this date the full picks card is paid, so the analysis
# page must not contain it at all (a CSS blur is not protection, the text is in the page source).
# Keep equal to PAYWALL_START_DATE in weekly-model/weekly_model_pipeline.py.
PAYWALL_START_DATE = "2027-01-21"


def paywall_active(start_date):
    return (start_date or "") >= PAYWALL_START_DATE


_CLIFF_RX = re.compile(r'<div class="cliff-blurred" id="cliff-content">.*?</div><!-- end cliff-content -->', re.S)
_CLIFF_EMPTY = ('<div class="cliff-blurred" id="cliff-content" aria-hidden="true" style="min-height:320px">'
                '</div><!-- end cliff-content -->')


def strip_paid_card(s):
    """Remove everything behind the content cliff (the full picks card, fade rows and the free-Substack strip)
    from an analysis page. The gate overlay and its paid pitch stay; an empty fixed-height placeholder keeps the
    overlay from collapsing. The sessionStorage honor-unlock is switched off since there is nothing to reveal."""
    s, k = _CLIFF_RX.subn(lambda m: _CLIFF_EMPTY, s, count=1)
    if k != 1:
        if 'id="cliff-content"' in s:
            raise SystemExit("could not strip the cliff content (unexpected markup)")
        raise SystemExit("no content cliff found on this page")
    s = s.replace("if(!isUnlocked()&&overlay){", "if(overlay){")
    if "Full Picks Card" in s:
        raise SystemExit("SAFETY: 'Full Picks Card' still in the page after stripping, aborted")
    return s


def section(s, marker):
    i = s.index(marker)
    j = s.index("</section>", i)
    return i, j


def apply(page, data, posted, dry, paywalled=False):
    s = open(page, encoding="utf-8", newline="").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    n = 0

    def sub(pattern, repl, text, flags=re.S):
        nonlocal n
        new, k = re.subn(pattern, lambda m: repl(m) if callable(repl) else repl, text, count=1, flags=flags)
        if k != 1:
            raise SystemExit("could not find: " + pattern[:70])
        n += 1
        return new

    # 02 counts
    s = sub(r"\d+ players had enough data to be scored and \d+ cleared the Winner DNA gates",
            "%d players had enough data to be scored and %d cleared the Winner DNA gates" % (data["n_scored"], data["n_pass"]), s)
    # 03 rows
    i, j = section(s, "03 — Top 3 Course Fits")
    seg = s[i:j]
    seg = sub_in(seg, r"<tbody>.*?</tbody>", "<tbody>\n" + data["rows03"] + "\n    </tbody>")
    s = s[:i] + seg + s[j:]
    # 04 featured
    i, j = section(s, "04 — Featured Pick")
    seg = s[i:j]
    a = re.search(r'<a href="https://strokesedge\.substack\.com"[^>]*>.*?</a>', seg, re.S)
    link = a.group(0) if a else ""
    seg = sub_in(seg, r'<div class="callout-label">.*?</div>', '<div class="callout-label">%s</div>' % esc(data["feat_name"]))
    seg = sub_in(seg, r'<div class="callout-text">.*?</div>',
                 '<div class="callout-text">%sFull odds, tier, and reasoning in the picks card below the gate. %s</div>' % (esc(data["feat_text"]), link))
    s = s[:i] + seg + s[j:]
    # 06 card (paid events: removed from the page entirely instead of refreshed)
    if paywalled:
        s = strip_paid_card(s)
    else:
        i, j = section(s, "06 — Full Picks Card")
        seg = s[i:j]
        seg = sub_in(seg, r'<p class="body-text">.*?</p>', '<p class="body-text">%s</p>' % esc(data["intro06"]))
        seg = sub_in(seg, r"<tbody>.*?</tbody>", "<tbody>\n" + data["card"] + "\n        </tbody>")
        if posted:
            seg = seg.replace("publish free on the StrokesEdge Substack", "are free on the StrokesEdge Substack")
        s = s[:i] + seg + s[j:]
    if posted:
        s = s.replace("publish on the Substack newsletter before Thursday's first tee shot", "are in the Substack newsletter now")
    # FAQ visible + structured data
    s = sub(r'(<div class="callout-label">Who is favored to win[^<]*</div>\s*<div class="callout-text">).*?(</div>)',
            lambda m: m.group(1) + esc(data["faq"]) + m.group(2), s)

    def ld(m):
        d = json.loads(m.group(1))
        for g in (d["@graph"] if "@graph" in d else [d]):
            if g.get("@type") == "FAQPage":
                for q in g["mainEntity"]:
                    if q["name"].startswith("Who is favored"):
                        q["acceptedAnswer"]["text"] = data["faq"]
        return '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False) + "</script>"
    s = sub(r'<script type="application/ld\+json">(.*?)</script>', ld, s)
    if not dry:
        open(page, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
    return n


def sub_in(text, pattern, repl):
    new, k = re.subn(pattern, lambda m: repl, text, count=1, flags=re.S)
    if k != 1:
        raise SystemExit("could not find: " + pattern[:60])
    return new


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("event")
    ap.add_argument("--year", default="2026")
    ap.add_argument("--posted", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--paywall", action="store_true", help="force the paid-launch layout (no picks card in the page), for testing")
    a = ap.parse_args()
    page = os.path.join(SITE, "analysis-%s-%s.html" % (a.event, a.year))
    if not os.path.exists(page):
        raise SystemExit("analysis page not found: " + page)
    p, ev, metrics, l1, l2, l3, tiers = load(a.event)
    data = build(p, ev, metrics, l1, l2, l3, tiers, a.posted)
    print(json.dumps(data["summary"], indent=1, ensure_ascii=False))
    paywalled = a.paywall or paywall_active(ev.get("start_date"))
    k = apply(page, data, a.posted, a.dry_run, paywalled)
    print("%s %d sections on %s" % ("would update" if a.dry_run else "updated", k, os.path.basename(page)))
