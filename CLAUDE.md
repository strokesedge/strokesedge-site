# StrokesEdge — Claude Code Instructions

## What This Site Is
StrokesEdge (strokesedge.com) is a PGA Tour golf betting analytics brand. Static HTML site hosted on Cloudflare Pages, deployed via GitHub repo `strokesedge/strokesedge-site`. Every push to `main` auto-deploys within 60 seconds.

---

## Repo Structure
All files live in the `Strokes Edge Website HTML/` subfolder inside the repo.

```
Strokes Edge Website HTML/
├── index.html                        ← Homepage (always shows current tournament)
├── analysis.html                     ← Main analysis hub (permanent, never delete)
├── picks.html                        ← Pick tracker (weekly access code gate)
├── methodology.html                  ← Model methodology
├── courses.html                      ← Course index
├── analysis-[tournament]-[year].html ← Archive analysis pages
├── course-[course-name].html         ← Course profile pages
├── sitemap.xml                       ← Must update when adding new pages
├── robots.txt
├── _headers
├── _redirects
└── favicon files (.ico, .png sizes)
```

**Note:** `potd.html` has been removed. Do not reference it anywhere.

---

## Weekly Tournament Update Protocol

When Brian says "Run the weekly update for [Tournament Name]" do ALL of the following automatically without asking for more information:

**Step 1 — Research**
- Search the web for tournament details: course name, location, par, yardage, dates, field size
- Search the web for course profile: layout type, primary defense, what SG stats matter, historical winner patterns, course conditions
- Fetch Substack RSS feed (https://strokesedge.substack.com/feed) to find that week's published article URL
- If Brian provides a Substack URL or Excel model file, use that as the primary source for picks and analysis content

**Step 2 — Update picks.html access code**
- Generate new code in format [TOURNAMENTSLUG][2-digit year] e.g. OPEN26, MASTERS26
- Add new code to validCodes array in picks.html (never remove old codes)
- Brian should include this code in his Substack newsletter

**Step 3 — Build all pages in one commit**
- Create course-[slug].html using course-quail-hollow.html as template
- Create analysis-[tournament-slug]-[year].html using analysis-pga-2026.html as template
- Update index.html hero to show current tournament
- Update analysis.html: new analysis becomes featured, previous featured moves to archive cards
- Update courses.html: new course card at top with GUIDE LIVE badge, previous top card flips to ARCHIVE
- Update sitemap.xml with both new pages
- Run pre-deploy audit before pushing
- Push everything in one commit

**What Brian provides (when available):**
- Tournament name (required)
- Substack article URL (optional but preferred for picks content)
- Excel model workbook (optional but preferred for exact picks/odds/rankings)

**If no model file or Substack provided:**
Generate analysis content from web research only. Use placeholder picks section with note "Full picks card published on Substack."

---

## What Is Free vs Gated

### Always Free (no gate, no CTA wall)
- index.html — homepage
- courses.html — course index
- course-[name].html — all course profile pages
- methodology.html — model methodology

### Gated
- picks.html — weekly access code gate
- Bottom half of every analysis page — content cliff with Substack gate

---

## Substack Gate Implementation

### picks.html — Weekly Access Code Gate

The pick tracker is locked behind a weekly access code distributed in the Substack newsletter.

Implementation:
- Full page overlay on load, cannot be dismissed or bypassed
- Headline: "WEEKLY ACCESS CODE"
- Subtext: "Find the code in this week's StrokesEdge Substack newsletter."
- Code input field + "Unlock" green button (#6ab83a)
- Below input, smaller text: "Not subscribed yet? Get free weekly picks at strokesedge.substack.com" (linked)
- On correct code: store unlock in sessionStorage, show tracker
- On wrong code: show error "Invalid code. Check this week's newsletter."
- Code check is case-insensitive
- Style: dark bg #080b07, green button #6ab83a, Bebas Neue headline, DM Sans body

**Code array in picks.html JS — never remove old codes, only add new ones:**
```javascript
const validCodes = ['SCOTTISH26','OPEN2026'];
// Add new code each week — never delete old ones
```

**Code naming format:** [TOURNAMENTSLUG][2-digit year]
Examples: SCOTTISH26, OPEN2026, MASTERS26

**Never:**
- Remove old codes from the array
- Add a bypass, dismiss, or honor-system email option
- Change gate to anything other than the code system

### Analysis Pages — Partial Block (Content Cliff)
The top half of every analysis page is free. Below the content cliff, content is blurred with a gate overlay.

Free section (always visible):
1. Course overview (yardage, par, key conditions)
2. What stats matter this week (SG categories and why)
3. Top 3 course fits — stat profile only, no odds, no pick tiers
4. One featured pick — name and one-sentence reason only

Content cliff — gate overlay appears here:
- Blurred content visible behind overlay (CSS blur, not hidden)
- Overlay text: "Get the full model breakdown free every week. Subscribe to StrokesEdge on Substack."
- Green Subscribe button linking to https://strokesedge.substack.com

Blurred section contains:
5. Full model rankings (all players scored)
6. Complete picks card with tiers — E/W Winner, Top 10/20/30, Longshot, Fade
7. Fade notes (always specify what market is faded and what remains valid)
8. Bankroll and odds notes
9. Link to full Substack article

---

## Model Sales Section

Appears on index.html (hero area) and every analysis page (just above the content cliff).

### Links
- Gumroad (weekly workbook): https://strokesedge.gumroad.com/l/buehoc — $7/tournament
- BuyMeACoffee (membership): https://buymeacoffee.com/strokesedge/membership — $21/month

### Buttons
- Primary (green #6ab83a fill): "Get Weekly Model — $7" → Gumroad
- Secondary (green outline): "Monthly Membership — $21/mo" → BuyMeACoffee
- Stack vertically on mobile, side by side on desktop

### Placement
- index.html: below hero, above archive cards
- Analysis pages: after top-3 free section, before content cliff/gate

---

## Pick Tracker Data

CSV URL:
```
https://docs.google.com/spreadsheets/d/e/2PACX-1vRn7eBjHWBs4nag5K5QHxnKiyeC-UEobNINAfjmEKsnBgX6aqm3lEZCY1i4lg5t5Lwy3I2p8ZLrR4Gc/pub?gid=0&single=true&output=csv
```

CSV columns: player, tournament, date, type, odds, wager, payout, result
- Date format: DD-Mon (e.g. 14-Apr)
- Odds stored without plus sign as plain integers
- Result values: open, won, lost, placed (lowercase only)
- Payout = total return including stake. 0 for open bets.

---

## Analysis Page Content Structure

```
[HEADER]
Tournament name, course, dates, location

[FREE — visible to all]
Section 1: Course Overview
- Par, yardage, course type
- Key playing conditions
- Historical winning scores

Section 2: What Stats Matter This Week
- Primary SG category with weighting
- Secondary categories with weightings
- Why these stats matter at this course

Section 3: Top 3 Course Fits
- Player name + stat profile only
- No odds, no pick tiers, no bet sizing
- One sentence on why the course fits

Section 4: Featured Pick
- One player, name only
- One sentence reason
- "Full breakdown on Substack →" link

[MODEL SALES SECTION]
$7 Gumroad / $21 BMAC buttons

[CONTENT CLIFF — gate overlay]
Subscribe to Substack CTA

[BLURRED BEHIND GATE]
Section 5: Full Model Rankings
Section 6: Complete Picks Card (all tiers)
Section 7: Fade notes
Section 8: Bankroll/odds notes
Section 9: Link to Substack article
```

---

## Standing Templates

- New analysis pages: use `analysis-pga-2026.html` as template
- New course pages: use `course-quail-hollow.html` as template

---

## Nav Standard

Nav is simplified — no dropdowns. Direct links only:
- Home → index.html
- Methodology → methodology.html
- Pick Tracker → picks.html
- Courses → courses.html
- Analysis → analysis.html
- Subscribe → https://strokesedge.substack.com (button style)

Mobile menu: same links, same order.

Every nav must have hamburger at `@media(max-width:860px)`.

---

## Responsive Breakpoints

- `@media(max-width:860px)` — hamburger nav
- `@media(max-width:640px)` — mobile layout
- `@media(max-width:380px)` — smallest screen (if stat grids used)

---

## Homepage (index.html) — Always Shows Current Tournament

Update every new tournament week:
1. Hero headline — current tournament name
2. Hero subtext — course name and dates
3. CTA button — links to new analysis page
4. Featured analysis card — current week

---

## File Naming

| Page type | Pattern |
|---|---|
| Analysis archive | `analysis-[tournament-slug]-[year].html` |
| Course profile | `course-[course-slug].html` |

---

## Title Tags

| Page | Formula |
|---|---|
| Analysis | `[Tournament] [Year] Analysis — StrokesEdge` |
| Course | `[Course Name] Betting Guide — [Tournament] \| StrokesEdge` |
| Homepage | `StrokesEdge — PGA Tour Golf Betting Analysis & Picks` |
| Methodology | `Golf Betting Model — How StrokesEdge Works \| StrokesEdge` |
| Picks | `PGA Tour Pick Tracker & Betting Record — StrokesEdge` |

---

## Sitemap Priorities

| Page | Priority | changefreq |
|---|---|---|
| Homepage | 1.0 | weekly |
| analysis.html | 0.9 | weekly |
| picks.html | 0.9 | weekly |
| courses.html | 0.8 | monthly |
| Course guides (current) | 0.8 | yearly |
| Course guides (past) | 0.7 | yearly |
| methodology.html | 0.7 | monthly |
| Archive analysis | 0.6 | never |

---

## Internal Linking

- Every analysis page → relevant course guide, picks.html, strokesedge.substack.com
- Every course guide → analysis.html, 2 other course guides, picks.html, methodology.html

---

## Writing Rules

- No em dashes in prose
- No AI-sounding parallel structure
- Data-forward, analytical tone
- Every page footer: "Not financial advice. Gamble responsibly."

---

## Pre-Deploy Audit — Run Before Every Commit

**Head Tags**
- Every page has specific `<meta name="description">`
- Every page has correct `<title>` tag
- Every page has `<link rel="canonical">` with correct URL
- Every page has OG and Twitter card meta tags
- Every page has GA4 tag `G-D398EHRP6Y` in `<head>`
- Every page has all 4 favicon link tags

**Gates**
- picks.html shows weekly access code gate — no bypass
- All analysis pages have content cliff blur gate
- Model sales section present on index.html and all analysis pages

**Responsive**
- `@media(max-width:860px)` hamburger breakpoint on every page
- `@media(max-width:640px)` mobile layout on every page

**Links**
- No broken internal links
- sitemap.xml includes all pages with correct priorities

**Footer**
- Every page has "Not financial advice. Gamble responsibly."

Fix all issues found before pushing.

---

## Automated Weekly Script

`weekly_course_update.py` runs every Sunday at 5pm automatically. It creates new course pages and updates courses.html and sitemap.xml. Never modify or delete this script. When manually updating the site, check `weekly_course_update.log` to see what the script last changed so you don't duplicate or conflict with its work.

---

## Substack Reference

RSS feed: https://strokesedge.substack.com/feed

Before writing any analysis page, fetch this RSS feed to find the latest published post. Use post titles and publish dates to link correctly to the right Substack article.

---

## Key URLs

- Live site: https://strokesedge.com
- GitHub: https://github.com/strokesedge/strokesedge-site
- Substack: https://strokesedge.substack.com
- Picks tracker: https://strokesedge.com/picks.html
- Gumroad: https://strokesedge.gumroad.com/l/buehoc
- BuyMeACoffee: https://buymeacoffee.com/strokesedge/membership
- Pick tracker CSV: https://docs.google.com/spreadsheets/d/e/2PACX-1vRn7eBjHWBs4nag5K5QHxnKiyeC-UEobNINAfjmEKsnBgX6aqm3lEZCY1i4lg5t5Lwy3I2p8ZLrR4Gc/pub?gid=0&single=true&output=csv
- GA4: G-D398EHRP6Y
- Contact: strokesedge@gmail.com
