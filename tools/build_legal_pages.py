"""
Builds privacy.html and terms.html and links them from every footer. Safe to re-run.

Both pages describe what the site actually does today (Google Analytics 4, the embedded Substack signup,
Gumroad and Buy Me a Coffee checkouts, Google Fonts, Cloudflare hosting, the Google Sheet behind the tracker).
If the site starts doing something new (accounts, a new processor, affiliate links, ads), update them.
They are plain-language drafts and should be read by someone qualified to give legal advice.
"""
import glob
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitepage import render_page, SITE  # noqa: E402

TODAY = date.today().strftime("%B %d, %Y").replace(" 0", " ")

PRIVACY = """
<div class="meta">Last updated __TODAY__</div>
<p>StrokesEdge (strokesedge.com) is a PGA Tour betting analysis site. This page explains what information we, and the services we use, collect when you visit or buy something, and why. The site has no accounts, passwords, comment sections or payment forms of its own.</p>

<h2>What we collect directly</h2>
<p>Nothing you type on this site is sent to us. If you email <a href="mailto:strokesedge@gmail.com">strokesedge@gmail.com</a>, we receive your email address and your message, and we use them to reply.</p>

<h2>Newsletter</h2>
<p>The signup form is Substack's, shown on our pages. Your email address is collected by Substack and we can see our subscriber list there. Substack's privacy policy applies to what they collect. Every newsletter email has an unsubscribe link.</p>

<h2>Purchases</h2>
<p>The $7 workbook is sold through Gumroad and the $21 membership through Buy Me a Coffee. They collect your name, email and payment details and process the payment. We receive order information from them, such as your email address and what you bought. We never see your full card number. Their privacy policies and terms apply to those purchases.</p>

<h2>Analytics</h2>
<p>We use Google Analytics 4 to see how the site is used. It records page views, approximate location, device and browser type, how you arrived and which buttons you click, using cookies or similar identifiers. We use this to learn which pages are useful. You can limit this through your browser settings or with Google's opt-out browser add-on.</p>

<h2>Other services that load when you visit</h2>
<ul>
<li><strong>Cloudflare</strong> hosts and protects the site. It processes your IP address and request logs for security and performance.</li>
<li><strong>Google Fonts</strong> delivers our typefaces, so Google receives your IP address when a page loads.</li>
<li><strong>Google Sheets</strong> holds the bet record that the Pick Tracker reads. That data is public bet information, not personal information. If your browser blocks the direct request, the page falls back to a public relay service (corsproxy.io) to fetch the same public data.</li>
<li><strong>Substack</strong> loads its signup form when you open it and may set its own cookies.</li>
<li>Links to X, Substack, Gumroad and Buy Me a Coffee take you to those services, which have their own privacy practices.</li>
</ul>

<h2>Data stored in your browser</h2>
<p>The site saves small flags in your browser's session storage, such as whether you have entered a weekly access code or chosen to show a locked section. They stay on your device and are cleared when the browser session ends. We do not receive them.</p>

<h2>How we use information</h2>
<p>We use information to run and improve the site, send the newsletter you asked for, fulfil purchases and answer your emails. We do not sell personal information.</p>

<h2>Who we share it with</h2>
<p>Only the service providers listed above, and authorities where the law requires it.</p>

<h2>How long we keep it</h2>
<p>Newsletter email addresses stay in Substack until you unsubscribe. Purchase records are kept by Gumroad and Buy Me a Coffee under their policies. Emails you send us are kept for as long as we need them to help you.</p>

<h2>Your choices and rights</h2>
<p>You can unsubscribe at any time using the link in any newsletter. You can email us to ask what we hold about you, to correct it, or to ask us to delete it. We hold very little, because most data sits with Substack, Gumroad, Buy Me a Coffee and Google, and you would need to contact them for data they hold. Depending on where you live, such as California, the European Economic Area or the United Kingdom, you may have additional legal rights over your information, and you can exercise them by emailing us.</p>

<h2>Age</h2>
<p>StrokesEdge is for adults aged 21 and over. We do not knowingly collect information from anyone under 21.</p>

<h2>Changes and contact</h2>
<p>We will update this page if our practices change and show the new date at the top. Questions: <a href="mailto:strokesedge@gmail.com">strokesedge@gmail.com</a>. See also the <a href="terms.html">Terms of Use</a>.</p>
""".replace("__TODAY__", TODAY)

TERMS = """
<div class="meta">Last updated __TODAY__</div>
<p>These terms apply to strokesedge.com and to the newsletter, workbooks and membership sold under the StrokesEdge name. By using the site you agree to them.</p>

<h2>Who can use StrokesEdge</h2>
<p>You must be 21 or older. Sports betting is not legal everywhere, and the rules differ by state and country. You are responsible for making sure that betting, and any use of this information, is legal where you live.</p>

<h2>Information only, not advice</h2>
<p>Everything on StrokesEdge is analysis for information and entertainment. It is not financial, investment or betting advice. StrokesEdge is not a sportsbook, does not accept bets and does not hold anyone's money. No pick, model score or probability is guaranteed. You can lose money betting. Past results, including the record on the <a href="picks.html">Pick Tracker</a>, do not predict future results. Only bet what you can afford to lose.</p>

<h2>Responsible gambling</h2>
<p>If gambling is a problem for you or someone you know, call 1-800-GAMBLER (US) for free, confidential help, or visit <a href="https://www.ncpgambling.org" target="_blank" rel="noopener">ncpgambling.org</a>. Outside the US, look for your national help line.</p>

<h2>Data and accuracy</h2>
<p>We use third-party data, including player statistics and sportsbook odds, which can be wrong, late or out of date. Odds move, markets close and fields change. Check the current price and terms with your sportsbook before you bet.</p>

<h2>Purchases</h2>
<p>The $7 workbook is sold through Gumroad and the $21 membership through Buy Me a Coffee. Their terms apply to the purchase and the payment. Workbooks are digital products for your own personal use. You may not share, resell or republish them. If something goes wrong with an order, email <a href="mailto:strokesedge@gmail.com">strokesedge@gmail.com</a>, and the refund rules of the platform you bought through also apply.</p>

<h2>Content and ownership</h2>
<p>The site, newsletter, workbooks and model outputs belong to StrokesEdge. You may quote short excerpts with a clear credit and a link back, but you may not copy whole pages, articles or workbooks.</p>

<h2>Third-party links and services</h2>
<p>We link to other sites and rely on other services. We are not responsible for them or for what they do.</p>

<h2>No warranties and limited liability</h2>
<p>The site and everything on it are provided as they are, without promises of accuracy, availability or fitness for any purpose. To the fullest extent the law allows, StrokesEdge is not liable for any loss, including betting losses, that results from using the site or acting on its content.</p>

<h2>Changes</h2>
<p>We may change these terms or the site at any time. The date at the top shows the latest version, and using the site after a change means you accept it. We may stop selling to anyone who misuses the workbooks or the site.</p>

<h2>Contact</h2>
<p><a href="mailto:strokesedge@gmail.com">strokesedge@gmail.com</a>. See also the <a href="privacy.html">Privacy Policy</a>.</p>
""".replace("__TODAY__", TODAY)

REL = [("about.html", "About StrokesEdge", "How the picks are made"),
       ("picks.html", "Pick Tracker", "Every bet, wins and losses"),
       ("methodology.html", "Methodology", "How the model works")]

if __name__ == "__main__":
    render_page("privacy.html", "Privacy Policy | StrokesEdge",
                "How StrokesEdge and the services it uses collect and use information: analytics, the newsletter form, purchases and your choices.",
                "Privacy <span>Policy.</span>", "What is collected when you visit strokesedge.com or buy from us, and why.",
                PRIVACY, "Legal", related=REL, schema="WebPage")
    render_page("terms.html", "Terms of Use | StrokesEdge",
                "The terms for using StrokesEdge: information only, no advice or guarantees, 21+, purchases through Gumroad and Buy Me a Coffee, and responsible gambling.",
                "Terms of <span>Use.</span>", "The rules for using the site, the newsletter and the workbooks.",
                TERMS, "Legal", related=REL, schema="WebPage")

    # footer links on every page (idempotent)
    about = '<a href="about.html">About</a>'
    add = about + '<a href="privacy.html">Privacy</a><a href="terms.html">Terms</a>'
    tail = 'for free, confidential help.</p>'
    new_tail = 'for free, confidential help. <a href="privacy.html">Privacy</a> and <a href="terms.html">Terms</a>.</p>'
    changed = 0
    for path in sorted(glob.glob(os.path.join(SITE, "*.html"))):
        name = os.path.basename(path)
        if name in ("favicon-head-snippet.html", "404.html"):
            continue
        s = open(path, encoding="utf-8", newline="").read()
        if add in s or new_tail in s:  # footer links already there (body links to the other page do not count)
            continue
        if about in s:
            t = s.replace(about, add)
        elif 'class="se-rg"' in s and tail in s:
            t = s.replace(tail, new_tail, 1)
        else:
            t = s
        if t != s:
            open(path, "w", encoding="utf-8", newline="").write(t)
            changed += 1
    print("built privacy.html and terms.html; footer links added on", changed, "pages")
