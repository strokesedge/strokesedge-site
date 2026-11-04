"""
Publish the free weekly RECAP / RESULTS articles from Substack on strokesedge.com.

    python tools/publish_recaps.py                # every recap or results post in the Substack feed
    python tools/publish_recaps.py vidantaworld   # only posts whose title contains this text

Recaps are already public and sent free from Substack, so the feed is the source (full text is in the feed). For each
post this writes <event>-<year>-recap-results.html (site theme, Article + BreadcrumbList data, related links),
adds it to the sitemap and to tools/recaps.json, rebuilds the weekly-recaps.html archive and makes a social image.
Paid or gated posts are never published: a feed item whose text is short (a teaser) is skipped.
Then review, commit the new pages, weekly-recaps.html, sitemap.xml, og/*.png and tools/recaps.json.
"""
import html
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sitepage import render_page, SITE, HOST, esc  # noqa: E402
from publish_picks import add_to_sitemap, CSS  # noqa: E402

REGISTRY = os.path.join(HERE, "recaps.json")
FEED = "https://strokesedge.substack.com/feed"
KEEP = {"p", "h2", "h3", "h4", "ul", "ol", "li", "strong", "b", "em", "i", "a", "blockquote", "table", "thead",
        "tbody", "tr", "th", "td", "br"}
DROP_BLOCKS = ("subscription-widget", "button-wrapper", "captioned-image", "image-link", "footnote", "pencraft", "share")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class Clean(HTMLParser):
    """Keeps a small set of text tags, drops Substack widgets, images, buttons and scripts."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.stack = [], 0, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "") or ""
        if self.skip or tag in ("figure", "button", "script", "style", "svg", "picture", "iframe", "form") or \
                any(k in cls for k in DROP_BLOCKS):
            if tag not in ("br", "img", "source", "input", "hr"):
                self.skip += 1
                self.stack.append(("skip", tag))
            return
        if tag == "br":
            self.out.append("<br>")
            return
        if tag in ("img", "hr", "source", "input"):
            return
        if tag in KEEP:
            href = a.get("href", "")
            if tag == "a":
                href = html.unescape(href or "")
                if not href.startswith("http"):
                    self.stack.append(("drop", tag))
                    return
                self.out.append('<a href="%s" rel="noopener">' % html.escape(href, quote=True))
            else:
                self.out.append("<%s>" % ("strong" if tag == "b" else "em" if tag == "i" else tag))
            self.stack.append(("keep", "strong" if tag == "b" else "em" if tag == "i" else tag))
        else:
            self.stack.append(("drop", tag))

    def handle_endtag(self, tag):
        if not self.stack:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][1] == tag or (tag in ("b", "i") and self.stack[i][1] in ("strong", "em")):
                kind, _ = self.stack[i]
                del self.stack[i:]
                if kind == "skip":
                    self.skip = max(0, self.skip - 1)
                elif kind == "keep":
                    self.out.append("</%s>" % ("strong" if tag == "b" else "em" if tag == "i" else tag))
                return

    def handle_data(self, data):
        if not self.skip:
            self.out.append(html.escape(data, quote=False))


def sanitize(content):
    c = Clean()
    c.feed(content)
    c.close()
    s = "".join(c.out)
    s = s.replace(" — ", ", ").replace("—", ", ")
    s = re.sub(r"<(h[234])><strong>(.*?)</strong></\1>", r"<\1>\2</\1>", s)
    s = re.sub(r"<(h[234])>\d+,\s*", r"<\1>", s)
    s = re.sub(r"<(p|li|h2|h3|h4|td|th|strong|em)>\s*</\1>", "", s)
    # drop leftover sharing / subscribe prompts
    s = re.sub(r"<p>\s*(Subscribe|Share|Leave a comment|Thanks for reading)[^<]*(<a[^>]*>[^<]*</a>[^<]*)*</p>", "", s, flags=re.I)
    s = re.sub(r"<table>", '<div class="tablewrap"><table>', s)
    s = s.replace("</table>", "</table></div>")
    return s.strip()


def slugify(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def fetch_feed():
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 (StrokesEdge publish_recaps)"})
    xml = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S):
        t = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", it, re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", it)
        c = re.search(r"<content:encoded><!\[CDATA\[(.*?)\]\]></content:encoded>", it, re.S)
        ds = re.search(r"<description><!\[CDATA\[(.*?)\]\]></description>", it, re.S)
        lk = re.search(r"<link>(.*?)</link>", it)
        if t and d and c:
            out.append({"title": html.unescape(t.group(1)).strip(), "date": datetime.strptime(d.group(1)[5:16].strip(), "%d %b %Y"),
                        "content": c.group(1), "desc": html.unescape(ds.group(1)).strip() if ds else "",
                        "link": lk.group(1) if lk else ""})
    return out


def is_recap(title):
    h = title.split(":")[0].lower()
    return bool(re.search(r"\b(recap|results)\b", h)) and "dfs" not in h


def seo_description(item, event, year):
    d = re.sub(r"\s+", " ", item["desc"]).strip()
    d = d.replace(" — ", ", ").replace("—", ", ")
    base = "%s %s recap and results: " % (event, year)
    cand = base + d[0].lower() + d[1:] if d else base + "how every StrokesEdge model pick finished, graded."
    if len(cand) > 160:
        cand = cand[:156].rsplit(" ", 1)[0].rstrip(",;:. ") + "..."
    if len(cand) < 110:
        cand += " Every pick graded against the final leaderboard."
    return cand[:160]


def related_for(event):
    ev = slugify(event)
    rel = []
    reg = json.load(open(os.path.join(HERE, "picks_articles.json"), encoding="utf-8"))
    pk = next((r for r in reg if r["file"].startswith(ev)), None)
    if pk:
        rel.append((pk["file"] + ".html", "The picks for this event", "Best bets and fades before the first tee shot"))
    if os.path.exists(os.path.join(SITE, "analysis-%s-2026.html" % ev)):
        rel.append(("analysis-%s-2026.html" % ev, "Event analysis", "Course overview, key stats and top fits"))
    rel.append(("picks.html", "Public pick tracker", "Every settled bet, wins and losses"))
    return rel[:3]


def load():
    return json.load(open(REGISTRY, encoding="utf-8")) if os.path.exists(REGISTRY) else []


def build_index(reg):
    reg = sorted(reg, key=lambda r: r["date"], reverse=True)
    cards = "".join('<a class="pk" href="%s.html"><small>%s</small><strong>%s</strong><span>%s</span></a>'
                    % (r["file"], datetime.strptime(r["date"], "%Y-%m-%d").strftime("%b %d, %Y").replace(" 0", " "),
                       esc(r["title"]), esc(r["summary"])) for r in reg)
    css = (".pks{display:grid;gap:12px;margin:1.5rem 0 2rem}.pk{display:block;text-decoration:none;background:var(--sur);"
           "border:1px solid var(--bdr2);border-radius:4px;padding:20px 22px}.pk:hover{border-color:var(--bdr)}"
           ".pk small{font:400 11px/1.3 'DM Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--g)}"
           ".pk strong{display:block;font:700 20px/1.25 'Archivo',sans-serif;font-stretch:104%;color:var(--txt);margin:8px 0 6px}"
           ".pk span{font-size:15px;color:var(--txt2)}")
    body = '<div class="pks">%s</div>' % cards + (
        '<p>Every recap grades each pick against the final leaderboard, wins and misses included. See the full '
        '<a href="picks.html">public pick tracker</a> or read the <a href="weekly-picks.html">weekly picks archive</a>.</p>')
    render_page("weekly-recaps.html", "PGA Tour Pick Results and Weekly Recaps | StrokesEdge",
                "Every StrokesEdge weekly recap: how the model's PGA Tour picks finished, graded against the final leaderboard, with wins and misses shown.",
                "Weekly PGA Tour <span>Recaps.</span>",
                "How every model pick finished, graded against the final leaderboard.",
                body, "Results archive", extra_css=css, schema="WebPage")
    add_to_sitemap("weekly-recaps", datetime.now().strftime("%Y-%m-%d"), "0.8", "weekly")


def publish(item):
    title = item["title"]
    head, _, rest = title.partition(":")
    event_year = re.sub(r"\s+(Recap|Results)\s*$", "", head.strip(), flags=re.I)
    ym = re.search(r"\b(20\d\d)\b", event_year)
    year = ym.group(1) if ym else str(item["date"].year)
    event = re.sub(r"\s*20\d\d\s*$", "", event_year).strip()
    text = sanitize(item["content"])
    if len(re.sub(r"<[^>]+>", "", text)) < 1500:
        print("skip (teaser or paywalled, too short):", title[:60])
        return None
    slug = "%s-%s-recap-results" % (slugify(event), year)
    fname = slug + ".html"
    seo_title = ("%s %s Recap: Results and Pick Grades" % (event, year))
    if len(seo_title) > 60:
        seo_title = "%s %s Recap and Pick Grades" % (event, year)
    if len(seo_title) > 60:
        seo_title = "%s %s Recap and Results" % (event, year)
    seo_title = seo_title[:60]
    desc = seo_description(item, event, year)
    pretty = item["date"].strftime("%b %d, %Y").replace(" 0", " ")
    h1 = "%s: <span>%s</span>" % (esc(head.strip()), esc(rest.strip())) if rest else esc(title)
    lede = re.sub(r"\s+", " ", item["desc"]).replace("—", ",") or desc
    render_page(fname, seo_title, desc, h1, esc(lede), '<div class="art">%s</div>' % text, "Recap and results",
                related=related_for(event), extra_css=CSS + ".art table{width:100%}.art a,.art p{overflow-wrap:anywhere}", schema="Article",
                meta=esc("Published %s" % pretty), og_image=HOST + "og/%s.png" % slug,
                article_dates={"published": item["date"].strftime("%Y-%m-%d")})
    reg = [r for r in load() if r["file"] != slug]
    reg.append({"file": slug, "title": head.strip(), "date": item["date"].strftime("%Y-%m-%d"), "summary": desc})
    json.dump(reg, open(REGISTRY, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    add_to_sitemap(slug, item["date"].strftime("%Y-%m-%d"), "0.7", "yearly")
    print("published", fname, "(%s)" % pretty)
    return slug


def main():
    only = sys.argv[1].lower() if len(sys.argv) > 1 else None
    items = [i for i in fetch_feed() if is_recap(i["title"]) and (not only or only in i["title"].lower())]
    done = [publish(i) for i in items]
    done = [d for d in done if d]
    if done:
        build_index(load())
        subprocess.run([sys.executable, os.path.join(HERE, "make_og_images.py")], check=False)
        subprocess.run([sys.executable, os.path.join(HERE, "add_signup.py")], check=False)
        print("done: %d recap page(s). Review, then commit and push." % len(done))
    else:
        print("nothing to publish")


if __name__ == "__main__":
    main()
