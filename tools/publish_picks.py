"""
Publish a weekly picks article on strokesedge.com (it is also sent from Substack).

    python tools/publish_picks.py world-wide-technology-championship
    python tools/publish_picks.py --all          # every weekly-model folder whose article is already on Substack

What it does for one event folder under weekly-model/:
  * reads substack_article_*.md (SEO block + article body)
  * REFUSES to publish unless that article is already live on the Substack feed (or --force),
    because the repo is public and the picks must reach subscribers first
  * drops the pick-tracker access-code footer, so the code stays an email-only perk, and checks
    the code string appears nowhere in the generated page
  * converts the Markdown to a StrokesEdge page (nav, theme, JSON-LD Article + FAQPage)
  * adds the page to the sitemap, regenerates weekly-picks.html (the archive), makes the page's
    social image, and wires the signup script
Then review, commit and push as usual.
"""
import argparse
import glob
import html
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sitepage import render_page, SITE, HOST, esc  # noqa: E402

REPO = os.path.dirname(HERE)
WEEKLY = os.path.join(REPO, "weekly-model")
REGISTRY = os.path.join(HERE, "picks_articles.json")
FEED = "https://strokesedge.substack.com/feed"
GUMROAD = "https://strokesedge.gumroad.com/l/buehoc"
BMAC = "https://buymeacoffee.com/strokesedge/membership"

CSS = "h1{font-size:clamp(32px,4.6vw,54px)!important}.art h3{font:700 18px/1.3 'Archivo',sans-serif;font-stretch:104%;margin:1.4rem 0 .35rem;color:var(--txt)}.art ul{margin-bottom:1.2rem}"


# ----------------------------------------------------------------------------- feed
def feed_items():
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 (StrokesEdge publish_picks)"})
    xml = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        t = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", m.group(1), re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", m.group(1))
        if t and d:
            out.append((html.unescape(t.group(1)).strip(), datetime.strptime(d.group(1)[5:16].strip(), "%d %b %Y")))
    return out


def find_on_substack(article_title, items):
    """Substack subjects are rewritten, so match on the part before the colon, e.g. 'X 2026 Picks'."""
    head = article_title.split(":")[0].strip().lower()
    event = re.split(r"\s+20\d\d\b", head)[0].strip()
    for t, d in items:
        low = t.lower()
        if low.startswith(head):
            return t, d
        # Substack subjects vary ("2026 Model Picks"), so also accept: same event, "picks", not a recap
        if (low.startswith(event + " 20") and "picks" in low.split(":")[0]
                and not any(w in low for w in ("recap", "results"))):
            return t, d
    return None


# ----------------------------------------------------------------------------- markdown
def parse_article(path):
    raw = open(path, encoding="utf-8").read().replace("\r\n", "\n")
    m = re.search(r"=== SEO METADATA.*?===+\n(.*?)\n=+\n", raw, re.S)
    seo = {}
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            seo[k.strip()] = re.sub(r"\s*\(\d+ chars\)\s*$", "", v.strip())
        body = raw[m.end():]
    else:
        body = raw
    code = re.search(r"access code this week:\s*(\S+)", raw)
    body = body.strip("\n")
    # drop the access-code / links footer
    cut = body.find("Pick tracker access code")
    if cut != -1:
        hr = body.rfind("\n---", 0, cut)
        body = body[:hr if hr != -1 else cut]
    return seo, body.strip(), (code.group(1) if code else None)


def inline(t):
    t = html.escape(t, quote=False)
    t = t.replace(" — ", ", ").replace("—", ", ")
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = t.replace("strokesedge.gumroad.com", '<a href="%s">strokesedge.gumroad.com</a>' % GUMROAD)
    t = t.replace("buymeacoffee.com/strokesedge", '<a href="%s">buymeacoffee.com/strokesedge</a>' % BMAC)
    return t


def convert(body):
    """Returns (lede_text, meta_text, body_html, faq_list)."""
    lines = body.split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines.pop(0)
    meta = ""
    if lines and "·" in lines[0]:
        meta = re.sub(r"\s{2,}", " ", lines.pop(0)).strip()
    # split FAQ off
    text = "\n".join(lines)
    faq = []
    fm = re.search(r"\n## FAQ\n(.*)$", "\n" + text, re.S)
    if fm:
        text = ("\n" + text)[:fm.start()].strip("\n")
        for qm in re.finditer(r"\*\*(.+?)\*\*\n(.+?)(?=\n\*\*|\Z)", fm.group(1).strip(), re.S):
            clean_a = re.sub(r"\s+", " ", qm.group(2)).strip().replace(" — ", ", ").replace("—", ", ")
            faq.append((qm.group(1).strip().replace(" — ", ", "), clean_a))
    blocks = re.split(r"\n\s*\n", text.strip())
    out, lede, ul = [], None, []
    in_promo = False

    def flush():
        nonlocal ul
        if ul:
            out.append("<ul>" + "".join("<li>%s</li>" % inline(x) for x in ul) + "</ul>")
            ul = []

    for blk in blocks:
        b = blk.strip()
        if not b:
            continue
        if b == "---":
            flush()
            in_promo = not in_promo
            continue
        if in_promo:
            out.append('<div class="callout"><p>%s</p></div>' % inline(re.sub(r"\s+", " ", b)))
            continue
        if b.startswith("---") and b.rstrip().endswith("---") and len(b) > 8:
            flush()
            out.append('<div class="callout"><p>%s</p></div>' % inline(re.sub(r"\s+", " ", b.strip("-\n "))))
            continue
        if b.startswith("---"):
            b = b.lstrip("-\n ")
        lines_b = b.split("\n")
        # section heading
        if lines_b[0].startswith("## "):
            flush()
            head = re.sub(r"^\d+\s*—\s*", "", lines_b[0][3:]).strip()
            out.append("<h2>%s</h2>" % inline(head))
            lines_b = lines_b[1:]
            if not lines_b:
                continue
        # content lines
        para = []
        for ln in lines_b:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("- "):
                if para:
                    out.append("<p>%s</p>" % inline(" ".join(para)))
                    para = []
                ul.append(s[2:])
                continue
            if re.fullmatch(r"\*\*[^*]+\*\*", s):
                flush()
                if para:
                    out.append("<p>%s</p>" % inline(" ".join(para)))
                    para = []
                out.append("<h3>%s</h3>" % inline(s.strip("*")))
                continue
            flush()
            para.append(s)
        if para:
            text_p = " ".join(para)
            if lede is None and not out:
                lede = re.sub(r"\*\*", "", text_p)
            else:
                out.append("<p>%s</p>" % inline(text_p))
    flush()
    return lede or "", meta, '<div class="art">' + "\n".join(out) + "</div>", faq


# ----------------------------------------------------------------------------- pipeline
def related_for(event_slug):
    rel = []
    ana = os.path.join(SITE, "analysis-%s-2026.html" % event_slug)
    if os.path.exists(ana):
        rel.append(("analysis-%s-2026.html" % event_slug, "Event analysis", "Course overview, key stats and top fits"))
        m = re.search(r'href="(course-[a-z0-9\-]+\.html)"', open(ana, encoding="utf-8").read())
        if m:
            rel.append((m.group(1), "Course betting guide", "What the course rewards"))
    rel.append(("pga-tour-betting-guide.html", "PGA Tour betting guide", "Markets, odds and strategy"))
    return rel[:3]


def load_registry():
    return json.load(open(REGISTRY, encoding="utf-8")) if os.path.exists(REGISTRY) else []


def save_registry(reg):
    json.dump(reg, open(REGISTRY, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def add_to_sitemap(slug, date_iso, priority, changefreq):
    sm = os.path.join(SITE, "sitemap.xml")
    s = open(sm, encoding="utf-8", newline="").read()
    loc = HOST + slug
    if "<loc>%s</loc>" % loc in s:
        return
    entry = ("  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n    <changefreq>%s</changefreq>\n"
             "    <priority>%s</priority>\n  </url>\n\n" % (loc, date_iso, changefreq, priority))
    s = s.replace("</urlset>", entry + "</urlset>", 1)
    open(sm, "w", encoding="utf-8", newline="").write(s)


def build_index(reg):
    reg = sorted(reg, key=lambda r: r["date"], reverse=True)
    cards = "".join(
        '<a class="pk" href="%s"><small>%s</small><strong>%s</strong><span>%s</span></a>'
        % (r["file"], datetime.strptime(r["date"], "%Y-%m-%d").strftime("%b %d, %Y").replace(" 0", " "), esc(r["title"]), esc(r["summary"]))
        for r in reg)
    css = (".pks{display:grid;gap:12px;margin:1.5rem 0 2rem}.pk{display:block;text-decoration:none;background:var(--sur);"
           "border:1px solid var(--bdr2);border-radius:4px;padding:20px 22px}.pk:hover{border-color:var(--bdr)}"
           ".pk small{font:400 11px/1.3 'DM Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--g)}"
           ".pk strong{display:block;font:700 20px/1.25 'Archivo',sans-serif;font-stretch:104%;color:var(--txt);margin:8px 0 6px}"
           ".pk span{font-size:15px;color:var(--txt2)}")
    body = '<div class="pks">%s</div>' % cards + (
        '<p>Every picks article is also emailed free before the event. <a href="results.html">See the public record</a> or read the '
        '<a href="pga-tour-betting-guide.html">PGA Tour betting guide</a>.</p>')
    render_page("weekly-picks.html", "Weekly PGA Tour Picks and Best Bets | StrokesEdge",
                "Every StrokesEdge weekly PGA Tour picks article in one place: model best bets, fades and the course stats behind each pick, free before every event.",
                "Weekly PGA Tour <span>Picks.</span>",
                "Model best bets and fades for every PGA Tour event, with the course stats behind each pick.",
                body, "Picks archive", extra_css=css, schema="WebPage")
    add_to_sitemap("weekly-picks", datetime.now().strftime("%Y-%m-%d"), "0.9", "weekly")


def publish(event_dir, force=False, feed=None):
    slug = os.path.basename(event_dir)
    arts = sorted(glob.glob(os.path.join(event_dir, "substack_article_*.md")))
    if not arts:
        print("no substack_article_*.md in", event_dir)
        return None
    seo, body, code = parse_article(arts[-1])
    title = seo.get("ARTICLE TITLE")
    page_slug = seo.get("POST URL")
    if not (title and page_slug):
        print("skipping %s: no SEO block (ARTICLE TITLE / POST URL) in %s" % (slug, os.path.basename(arts[-1])))
        return None
    feed = feed if feed is not None else feed_items()
    hit = find_on_substack(title, feed)
    if not hit and not force:
        print("NOT published on Substack yet, skipping %s (use --force to override)" % slug)
        return None
    date = hit[1] if hit else datetime.now()
    lede, meta, body_html, faq = convert(body)
    fname = page_slug + ".html"
    d = seo.get("SEO DESCRIPTION", "")
    if len(d) > 160:  # the pipeline's own SEO block can run long, trim at a word boundary like Google would
        seo["SEO DESCRIPTION"] = d[:156].rsplit(" ", 1)[0].rstrip(",;:") + "..."
    pretty = date.strftime("%b %d, %Y").replace(" 0", " ")
    meta_line = ("Published %s · %s" % (pretty, meta)) if meta else "Published %s" % pretty
    head, _, rest = title.partition(":")
    h1 = "%s: <span>%s</span>" % (esc(head), esc(rest.strip())) if rest else esc(title)
    path = render_page(fname, seo.get("SEO TITLE", title)[:60], seo["SEO DESCRIPTION"], h1,
                       esc(lede) if lede else esc(seo["SEO DESCRIPTION"]), body_html, "Picks and best bets",
                       faq=faq, related=related_for(slug),
                       extra_css=CSS, schema="Article", meta=esc(meta_line), og_image=HOST + "og/%s.png" % page_slug,
                       article_dates={"published": date.strftime("%Y-%m-%d")})
    out = open(path, encoding="utf-8").read()
    if code and code in out:
        os.remove(path)
        raise SystemExit("SAFETY: the access code %s appears in the generated page, aborted" % code)
    reg = [r for r in load_registry() if r["file"] != fname.replace(".html", "")]
    reg.append({"file": fname.replace(".html", ""), "title": head.strip() if rest else title,
                "date": date.strftime("%Y-%m-%d"), "summary": seo["SEO DESCRIPTION"]})
    save_registry(reg)
    add_to_sitemap(page_slug, date.strftime("%Y-%m-%d"), "0.8", "monthly")
    print("published", fname, "(%s)" % pretty)
    return page_slug


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("event", nargs="?", help="folder name under weekly-model/")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true", help="publish even if not found on Substack (use only when sure)")
    a = ap.parse_args()
    feed = feed_items()
    dirs = ([os.path.join(WEEKLY, a.event)] if a.event else
            sorted(d for d in glob.glob(os.path.join(WEEKLY, "*")) if os.path.isdir(d))) if (a.event or a.all) else []
    if not dirs:
        ap.error("give an event folder name or --all")
    done = [publish(d, a.force, feed) for d in dirs]
    done = [d for d in done if d]
    if done:
        build_index(load_registry())
        subprocess.run([sys.executable, os.path.join(HERE, "make_og_images.py")], check=False)
        subprocess.run([sys.executable, os.path.join(HERE, "add_signup.py")], check=False)
        print("done:", len(done), "article(s). Review, then commit and push.")


if __name__ == "__main__":
    main()
