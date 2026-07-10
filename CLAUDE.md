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
├── picks.html                        ← Pick tracker (Substack gate — full block)
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

## What Is Free vs Gated

### Always Free (no gate, no CTA wall)
- index.html — homepage
- courses.html — course index
- course-[name].html — all course profile pages
- methodology.html — model methodology

### Substack Gate (full block — visitor must subscribe or enter email)
- picks.html — pick tracker
- Bottom half of every analysis page (see Analysis Page Structure below)

### Model Sales (Gumroad / BuyMeACoffee)
- Full Excel workbook with all model tabs, charts, value screen, weights
- Linked from homepage and all analysis pages

---

## Substack Gate Implementation

### picks.html — Weekly Access Code Gate

The pick tracker is locked behind a weekly access code. Codes are distributed in the StrokesEdge Substack newsletter each week. Only subscribers who read the newsletter can access the tracker.

**Current valid code:** SCOTTISH26

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
const validCodes = ['SCOTTISH26'];
// Add new code each week — never delete old ones
```

**Code naming format:** [TOURNAMENTSLUG][2-digit year]
Examples: SCOTTISH26, USOPEN26, MASTERS26, PGATOUR26

**Weekly code update workflow:**
1. Brian provides the new tournament name
2. Generate new code in format above
3. Add new code to validCodes array in picks.html
4. Push picks.html to GitHub
5. Include the code in that week's Substack newsletter

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
- Overlay text:
  ```
  Get the full model breakdown free every week.
  Subscribe to StrokesEdge on Substack.

  [Subscribe Free →]  (links to https://strokesedge.substack.com)
  ```
- Below the blurred section label: "Full model rankings · Complete picks card · Betting strategy"
- Same email honor-system unlock as picks.html

Blurred section contains (shown blurred, unlocked by email entry):
5. Full model rankings (all players scored)
6. Complete picks card with tiers — E/W Winner, Top 10/20/30, Longshot, Fade
7. Fade notes (always specify what market is faded and what remains valid)
8. Bankroll and odds notes
9. Link to full Substack article for complete reasoning

---

## Model Sales Section

Appears on index.html (hero area) and every analysis page (just above the content cliff).

### Links
- Gumroad (weekly workbook): https://strokesedge.gumroad.com/l/buehoc — $7/tournament
- BuyMeACoffee (membership): https://buymeacoffee.com/strokesedge/membership — $21/month

### Section Copy
```
Want the full model breakdown?
$7 per tournament — Weekly Model Workbook
$21/month — Monthly Membership (all main events)
```

### Buttons
- Primary (green `#6ab83a` fill): "Get Weekly Model — $7" → Gumroad
- Secondary (green outline): "Monthly Membership — $21/mo" → BuyMeACoffee
- Stack vertically on mobile, side by side on desktop

### Placement
- index.html: below hero, above archive cards
- Analysis pages: after top-3 free section, before content cliff/gate

---

## Pick Tracker Data

The pick tracker pulls from a public Google Sheet CSV. Claude Code can fetch this anytime.

CSV URL:
```
https://docs.google.com/spreadsheets/d/e/2PACX-1vRn7eBjHWBs4nag5K5QHxnKiyeC-UEobNINAfjmEKsnBgX6aqm3lEZCY1i4lg5t5Lwy3I2p8ZLrR4Gc/pub?gid=0&single=true&output=csv
```

CSV columns: player, tournament, date, type, odds, wager, payout, result
- Date format: DD-Mon (e.g. 14-Apr)
- Odds stored without plus sign as plain integers
- Result values: open, won, lost, placed (lowercase only)
- Payout = total return including stake. 0 for open bets.

When updating picks.html, fetch this CSV to get current data. Never hardcode pick data.

---

## Analysis Page Content Structure

Every analysis page follows this exact structure:

```
[HEADER]
Tournament name, course, dates, location

[FREE — visible to all]
Section 1: Course Overview
- Par, yardage, course type
- Key playing conditions (wind exposure, rough, greens)
- Historical winning scores

Section 2: What Stats Matter This Week
- Primary SG category (e.g. SG: Approach) with weighting
- Secondary categories with weightings
- Why these stats matter at this specific course
- One or two stats to fade (and why)

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
"Get the full model breakdown free. Subscribe on Substack."
Email field + Subscribe button

[BLURRED BEHIND GATE]
Section 5: Full Model Rankings
Section 6: Complete Picks Card (all tiers)
Section 7: Fade notes
Section 8: Bankroll/odds notes
Section 9: Link to Substack article
```

---

## Standing Template

Use `analysis-pga-2026.html` as the standing template for all new analysis pages. Match its exact structure, nav, CSS classes, and section layout. Update content only.

For course pages, use `course-quail-hollow.html` as the standing template.

---

## Nav Standard — CRITICAL

### Dropdown JS Requirements
Every nav dropdown must have BOTH:
```javascript
e.preventDefault();
e.stopPropagation();
```

### Nav Links (always in this order)
- Home → index.html
- Analysis (dropdown) — newest page always first
- Courses (dropdown) — newest page always first
- Picks → picks.html
- Methodology → methodology.html

### When Adding Any New Page
Update the nav dropdown on ALL existing HTML files in the same commit.

---

## Responsive Breakpoints

Always check all three:
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

Brian provides tournament name, course, and dates when ready.

---

## Weekly Update Checklist

One commit covers all of this:

- [ ] Create new analysis-[tournament]-[year].html
- [ ] Create new course-[course].html if needed
- [ ] Update Analysis dropdown on EVERY .html file (new page at top)
- [ ] Update Courses dropdown on EVERY .html file if new course added
- [ ] Update index.html hero to current tournament
- [ ] Update analysis.html archive cards (new card at top)
- [ ] Update sitemap.xml
- [ ] Confirm model sales section on index.html and new analysis page
- [ ] Confirm Substack gate on picks.html is working
- [ ] Confirm content cliff gate on new analysis page is working
- [ ] Verify all dropdowns on mobile and desktop
- [ ] Verify responsive breakpoints

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

---

## Pre-Deploy Audit — Run Before Every Commit

Before pushing any changes, audit ALL HTML files and fix every issue found in the same commit:

**Nav & Dropdowns**
- Every dropdown trigger has both `e.preventDefault()` AND `e.stopPropagation()`
- Analysis dropdown present and working on every page
- Courses dropdown present and working on every page
- Mobile hamburger menu works and contains all same links as desktop
- Newest analysis page is first in Analysis dropdown on every page
- Newest course page is first in Courses dropdown on every page
- No reference to potd.html anywhere

**Head Tags**
- Every page has `<meta name="description">` specific to that page
- Every page has correct `<title>` tag matching formula
- Every page has `<link rel="canonical">` with correct full URL
- Every page has OG and Twitter card meta tags
- Every page has GA4 tag `G-D398EHRP6Y` in `<head>`
- Every page has all 4 favicon link tags

**Gates**
- picks.html shows full Substack block gate — no email field, no bypass, Substack button only
- All analysis pages have content cliff blur gate at correct position
- Model sales section ($7/$21 buttons) present on index.html and all analysis pages

**Responsive**
- `@media(max-width:860px)` hamburger breakpoint on every page
- `@media(max-width:640px)` mobile layout on every page

**Links**
- No broken internal links
- No links pointing to pages that don't exist
- sitemap.xml includes all pages with correct priorities

**Footer**
- Every page has "Not financial advice. Gamble responsibly." in footer

Fix all issues found before pushing.

---

## Substack Reference

RSS feed: https://strokesedge.substack.com/feed

Before writing any analysis page or referencing recent articles, fetch this RSS feed to see the latest published posts. Use post titles and publish dates to link correctly to the right Substack article from each analysis page.
