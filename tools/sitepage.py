"""
Shared page builder for generated StrokesEdge content pages (calculators, cheat sheet landing,
picks articles). It uses the live pga-tour-betting-guide.html as the skeleton, so nav, footer,
theme and scripts always match the rest of the site, and swaps in the head tags, JSON-LD and body.
"""
import html as _html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "Strokes Edge Website HTML")
HOST = "https://strokesedge.com/"
SKELETON = os.path.join(SITE, "pga-tour-betting-guide.html")

SIGNUP = ('<div class="cta-box"><h2>Get the free picks every tournament week</h2>'
          '<p>One email before each PGA Tour event with the strokes gained model\'s picks and the course breakdown. '
          'The full model workbook is $7 per tournament.</p>'
          '<a class="btn" href="https://strokesedge.substack.com" data-signup>Subscribe free →</a>'
          '<a class="btn ghost" href="analysis.html">This week\'s analysis</a></div>')


def esc(t):
    return _html.escape(t, quote=True)


def _skeleton():
    s = open(SKELETON, encoding="utf-8").read()
    i, j = s.index("<main>"), s.index("</main>")
    return s[:i], s[j + len("</main>"):]


def render_page(slug, title, desc, h1, lede, body, eyebrow, faq=None, related=None, extra_css="",
                extra_js="", schema=None, meta="", noindex=False, og_image=None, article_dates=None, subtitle=None):
    """Writes SITE/<slug>.html and returns the path. h1 may contain <span>accent</span>."""
    assert len(title) <= 60, (slug, len(title))
    assert 110 <= len(desc) <= 160, (slug, len(desc))
    pre, post = _skeleton()
    url = HOST + slug.replace(".html", "")
    og = og_image or HOST + "og-image.png"

    def sub(pattern, repl, text):
        return re.sub(pattern, lambda m: m.group(1) + repl + m.group(2), text, count=1, flags=re.S)

    pre = sub(r"(<title>).*?(</title>)", esc(title), pre)
    pre = sub(r'(<meta name="description" content=").*?(">)', esc(desc), pre)
    pre = sub(r'(<link rel="canonical" href=").*?(">)', url, pre)
    pre = sub(r'(<meta property="og:url" content=").*?(">)', url, pre)
    pre = sub(r'(<meta property="og:title" content=").*?(">)', esc(title), pre)
    pre = sub(r'(<meta property="og:description" content=").*?(">)', esc(desc), pre)
    pre = sub(r'(<meta property="og:image" content=").*?(">)', og, pre)
    pre = sub(r'(<meta name="twitter:title" content=").*?(">)', esc(title), pre)
    pre = sub(r'(<meta name="twitter:description" content=").*?(">)', esc(desc), pre)
    pre = sub(r'(<meta name="twitter:image" content=").*?(">)', og, pre)
    if noindex:
        pre = pre.replace('<meta name="robots" content="index, follow">', '<meta name="robots" content="noindex, follow">')

    plain_h1 = re.sub(r"<[^>]+>", "", h1)
    org = {"@type": "Organization", "name": "StrokesEdge", "url": HOST}
    pub = dict(org, logo={"@type": "ImageObject", "url": HOST + "favicon-512x512.png"})
    graph = []
    if schema == "WebApplication":
        graph.append({"@type": "WebApplication", "name": plain_h1, "url": url, "description": desc,
                      "applicationCategory": "UtilitiesApplication", "operatingSystem": "Any",
                      "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "publisher": org})
    elif schema == "Article":
        d = article_dates or {}
        graph.append({"@type": "Article", "headline": plain_h1, "description": desc, "url": url,
                      "mainEntityOfPage": url, "image": og,
                      "datePublished": d.get("published", ""), "dateModified": d.get("modified", d.get("published", "")),
                      "author": org, "publisher": pub})
        if subtitle:
            graph[-1]["alternativeHeadline"] = subtitle
    else:
        graph.append({"@type": "WebPage", "name": title, "description": desc, "url": url, "publisher": org})
    graph.append({"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": HOST},
        {"@type": "ListItem", "position": 2, "name": plain_h1, "item": url}]})
    faq_html = ""
    if faq:
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})
        faq_html = "<h2>FAQ</h2>\n" + "".join(
            '<details class="faq-item"><summary>%s</summary><p>%s</p></details>\n' % (esc(q), esc(a)) for q, a in faq)
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)
    pre = re.sub(r'<script type="application/ld\+json">.*?</script>',
                 lambda m: '<script type="application/ld+json">' + ld + "</script>", pre, count=1, flags=re.S)
    if extra_css:
        pre = pre.replace('<link rel="stylesheet" href="se-theme.css">',
                          "<style>" + extra_css + '</style>\n<link rel="stylesheet" href="se-theme.css">', 1)
    rel_html = ""
    if related:
        rel_html = '<h2>Keep reading</h2>\n<div class="related">' + "".join(
            '<a href="%s">%s<small>%s</small></a>' % (u, esc(t), esc(d)) for u, t, d in related) + "</div>"
    meta_html = '<div class="meta hero-meta">%s</div>\n' % meta if meta else ""
    main = ('<main>\n<div class="eyebrow">%s</div>\n<h1>%s</h1>\n<p class="lede">%s</p>\n%s%s\n%s\n%s\n%s\n</main>'
            % (esc(eyebrow), h1, lede, meta_html, body, faq_html, SIGNUP, rel_html))
    out = pre + main + post
    if extra_js:
        out = out.replace("</body>", extra_js + "\n</body>", 1)
    path = os.path.join(SITE, slug)
    open(path, "w", encoding="utf-8", newline="").write(out)
    return path
