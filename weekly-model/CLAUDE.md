# StrokesEdge Weekly Model Pipeline — Claude Code Instructions

## What This Pipeline Is
A **fully unattended, scheduled** weekly golf model pipeline that pulls Data Golf data (and, on weeks it's added, a PGA Tour CSV supplement), runs the StrokesEdge L1/L2/L3 model, and produces the Excel workbook (Cover, Dashboard, Picks Card, Value Screen, Model Rankings, Watch List, Model Weights). Runs via Windows Task Scheduler, the same way `weekly_course_update.py` already runs — nobody triggers it by typing into a Claude Code session.

**This pipeline is intentionally separate from `strokesedge-site`.** It outputs the `.xlsx` workbook and nothing else — it does not touch the site repo, does not update picks.html access codes, and does not push analysis pages. It also does not integrate with "the workbook sender" — that's a separate Google Apps Script running in Google's cloud, outside this filesystem entirely, and out of scope here. This pipeline's handoff ends at emailing Brian the finished workbook as an attachment (see step 5 under Automation & Scheduling) — whatever the Apps Script does with it downstream is not this pipeline's concern.

**Status: this file is a draft for review. No pipeline code exists yet.**

### Reused infrastructure (already working, confirmed in this environment)
- `ANTHROPIC_API_KEY` — already set as a Windows env var, already used unattended by `weekly_course_update.py`'s `generate_analysis()` for its own Claude API call. This pipeline reuses the same pattern for the weight-proposal step (see below).
- `GMAIL_APP_PASSWORD` — already set, already used unattended by `weekly_course_update.py`'s `send_email()` (SMTP over `smtplib`, not the Claude Code Gmail MCP tool — that only works inside an interactive session, which this pipeline never has). Reuse the same function.
- `DATAGOLF_API_KEY` — already set, verified working this session (see below).
- Lock-file concurrency guard (`os.open(..., O_CREAT | O_EXCL)`), logging setup (UTF-8 file handler + degraded console output for Task Scheduler's non-UTF-8 codepage), and the "hold locally, email a summary, human does the final send" philosophy — all copied from `weekly_course_update.py` rather than reinvented. See Automation & Scheduling below.

---

## Data Golf API — Verified Working

`DATAGOLF_API_KEY` is already set in the environment and was live-tested against multiple endpoints during this session (`get-player-list`, `betting-tools/outrights`, `preds/skill-ratings`, `preds/player-decompositions`, `preds/pre-tournament`, `historical-raw-data/rounds`, `field-updates`, `get-schedule` all returned real data). Base URL: `https://feeds.datagolf.com/`. Key is passed as a `key` query param. Rate limit: 45 requests/minute, 5-minute suspension if exceeded — the pipeline should throttle/batch calls accordingly.

Never hardcode the key in scripts. It's already an environment variable; if a `.env` file is added for local dev, confirm `weekly-model/.env` is in `.gitignore` before first commit.

### Full endpoint inventory (what this pipeline actually uses)

| Endpoint | What it gives | Granularity | PGA Tour equivalent? |
|---|---|---|---|
| `preds/skill-ratings` | `sg_app`, `sg_ott`, `sg_arg`, `sg_putt`, `sg_total`, `driving_acc`, `driving_dist` per player | DG's proprietary rolling window (not season-to-date, not a selectable L30/L6mo) | Yes, but **numbers don't agree** — see SG Methodology below. `driving_acc`/`driving_dist` are SG-style ratings, not raw %/yards, so not a like-for-like swap for those specific columns. |
| `preds/approach-skill?period=l24\|l12\|ytd` | Proximity, GIR rate, good/poor shot rate, SG-per-shot — broken out by 6 distance/lie buckets: `50_100_fw`, `100_150_fw`, `150_200_fw`, `over_200_fw`, `under_150_rgh`, `over_150_rgh` | 50-yard bands only; no native L30/L6mo period (only l24/l12/ytd) | Partial — PGA Tour's proximity bands are 25-yard (100-125, 125-150, 150-175, 175-200, 200+) so DG is coarser. The `_rgh` buckets (rough recovery) have no PGA Tour equivalent at all. |
| `preds/player-decompositions` | Data Golf's own pre-tournament course-fit model, per player: `course_history_adjustment`, `course_experience_adjustment`, `driving_accuracy_adjustment`, `driving_distance_adjustment`, `cf_approach_comp`, `cf_short_comp`, `major_adjustment`, `age_adjustment`, `country_adjustment`, `timing_adjustment`, `strokes_gained_category_adjustment`, plus `baseline_pred`/`final_pred` (DG's own predicted SG for the event) | Per player, per upcoming event, all in strokes-gained-vs-average-field units | DG-exclusive. No PGA Tour equivalent — this replaces what used to be manual research for "course history" and "course fit." |
| `preds/get-dg-rankings` | DG's own world ranking + `dg_skill_estimate` | Current snapshot | DG-exclusive (OWGR is a different, publicly available ranking) |
| `preds/pre-tournament` | DG's own baseline win/top5/top10/top20/make-cut probabilities (as odds), pre-tournament | Per event | DG-exclusive |
| `betting-tools/outrights?market=win\|top_5\|top_10\|top_20\|mc\|make_cut\|frl` | **Real sportsbook odds** (not DG's model) from up to 13 books incl. DraftKings, FanDuel, BetMGM, Caesars, bet365 | Per market, live, confirmed working | DG-exclusive — PGA Tour doesn't publish odds |
| `betting-tools/matchups?market=tournament_matchups\|round_matchups\|3_balls` | Real sportsbook matchup/3-ball odds | Per market; **matchups typically don't post until Tuesday/Wednesday of tournament week** (confirmed empirically — tried mid-week and got "No matchups being offered right now" for finish markets that hadn't posted yet) | DG-exclusive |
| `historical-raw-data/rounds?tour=pga&event_id=all&year=YYYY` | Round-level data per player per round: `sg_app/arg/ott/putt/t2g/total`, `driving_acc`, `driving_dist`, `gir`, `scrambling`, `birdies`, `eagles_or_better`, `bogies`, `doubles_or_worse`, `prox_fw`, `prox_rgh`, with `event_completed` dates | Round-level, dated — this is the raw material for any custom rolling window | Overlaps with PGA Tour CSVs conceptually, but is DG's own scoring/SG methodology, not PGA Tour's |
| `field-updates?tour=pga` | Current week's confirmed field, tee times, DG rank, OWGR rank | Per event | Roughly matches PGA Tour's field list page |
| `get-schedule?tour=pga` | Full season schedule with course, dates, status, winner | Season | Roughly matches PGA Tour's schedule page |
| `historical-event-data/events`, `historical-odds/*`, `historical-dfs-data/*` | Historical event stats, historical odds archive, DFS points/salaries **for completed events only** — confirmed by testing: `historical-dfs-data/points?event_id=525&year=2026` (2026 3M Open, this week's event) 404s with "event number 525 is not available in the 2026 pga calendar year" because the event hasn't been played yet; the same call against `year=2025` (completed) returns real salary/points/ownership data. This is keyed by finish position, so it structurally can't exist before a tournament ends. | Various | Available for backtesting; **not usable for current-week DFS salaries** — see `preds/fantasy-projection-defaults` below for that. |
| `preds/fantasy-projection-defaults?tour=pga&site=draftkings&slate=main` | **Current-week DraftKings salaries** plus DK's own point/ownership projections, per player (`dg_id`-keyed): `salary`, `proj_points_total`, `proj_ownership`, `value` (projected points per $1,000 salary — DK's own efficiency metric), `site_name_id`. Confirmed live for the 2026 3M Open (queried the Wednesday before a Thursday start, `last_updated` timestamped same-day) — this is a separate, undocumented-in-earlier-drafts endpoint from `historical-dfs-data`, not a variant of it. | Per event, released a few days ahead of the tournament (exact lead time not yet observed across multiple weeks) | DG-exclusive — this is the answer to "does Data Golf have current-week DK salaries," and the answer is yes, just not via the endpoint this file originally pointed to. |

### Computed (not a single API call, built from `historical-raw-data/rounds`)
- **L30 recent-form window** — pull the year's rounds, filter to `event_completed` within the trailing 30 days, average `sg_app/arg/ott/putt` per player. Requires a minimum round count before treating the average as signal (mirrors the sample-size-scaled course-history weighting from past workbooks: too few recent rounds = no signal, not a bad signal).
- **Birdie or Better %** — `(birdies + eagles_or_better) / holes_played`, summed across the chosen window. No dedicated DG endpoint for this.

### The-Odds-API (the-odds-api.com) — pending, secondary
Brian is signing up but doesn't have a key yet. Since Data Golf's `betting-tools` endpoints already provide live, multi-book sportsbook odds for every market this model needs (outrights, matchups, finish positions), The Odds API isn't currently load-bearing. Once the key exists, treat it as a cross-check/fallback if a Data Golf odds pull is ever thin on a given week, not a primary dependency. Revisit this once the key is available.

---

## PGA Tour CSVs — Optional Weekly Supplement, Not a Standing Requirement

Automating everything Data Golf can provide is the priority. PGA Tour CSVs are added manually only on weeks where they'd meaningfully improve the model — flag this per-week, don't require it.

**Confirmed mechanics:** since the pipeline runs unattended, it checks for a dropped CSV file at `weekly-model/[tournament-slug]/pga_tour_supplement.csv` (or similar) **at firing time** — specifically at step 1 (field pull) and again at step 3 (L1/L2 regression, since Brian might drop it after the weight-proposal email goes out but before regression runs). If present, use it for the categories it covers (proximity bands, etc.); if absent by the time regression actually runs, proceed Data-Golf-only and note on the Model Weights sheet that no supplement was used that week.

**Where PGA Tour CSVs would actually help** (things Data Golf's API can't match):
- **Exact 25-yard proximity bands** (100-125, 125-150, 150-175, 175-200, 200+) — DG's `approach-skill` only has 50-yard bands (100-150, 150-200). If a course's Model Weights call for a specific 25-yard band (like TPC Deere Run's PROX 125-150 at 10% weight), that number can only come from a PGA Tour CSV.
- Anything where Brian specifically wants the PGA Tour's own official SG number cited alongside DG's, e.g. for public-facing credibility on the Substack write-up.

**Scraping pgatour.com directly was tested and works technically** — the site's stat tables load via an internal `orchestrator.pgatour.com/graphql` API, invisible to a plain HTTP fetch, but a rendered browser session (headless browser, JS executed) can read the fully-rendered table text cleanly. That said: this is undocumented, unofficial, and likely against PGA Tour's Terms of Service for automated collection. Default to manual CSV drops (Brian downloads and drops a file in when he wants the supplement); don't build automated scraping against pgatour.com without an explicit decision to accept that risk.

---

## SG Methodology

**Data Golf's "True SG" is not the same stat as PGA Tour's official SG, even though they share a name and similar scale.** Verified directly this session — pulling the same players' season SG:Approach from both sources:

| Player | PGA Tour SG:APR (season) | Data Golf `sg_app` | 
|---|---|---|
| Scheffler | +0.545 | +1.028 |
| Fleetwood | +0.326 | +0.642 |
| McIlroy | +0.396 | +0.575 |
| Fitzpatrick | +0.846 | +0.913 |
| Morikawa | +0.842 | +0.810 |

Some players are close, some differ by roughly 2x. PGA Tour computes SG per-event against that week's field only; Data Golf's "True SG" is a proprietary, field-strength-adjusted calculation blended across a rolling window and multiple tours. **These are not interchangeable.**

Given the priority on Data Golf-first automation, the pipeline runs on **Data Golf's own scale throughout** — do not mix a PGA-Tour-calibrated gate threshold with a Data-Golf-sourced stat value, or vice versa. This means:
- All L2 gate thresholds are calibrated against Data Golf's numbers specifically (the Open Championship file's gates — `APP >= -0.10`, `ACC >= -0.08` — are already DG-scale, notably looser-looking than the John Deere workbook's PGA-Tour-scale gates like `APP(B) >= +0.20`. That's expected, not a mistake — different scale, different thresholds.)
- If a PGA Tour CSV is added as a supplement in a given week (e.g. for proximity bands), it feeds categories DG doesn't cover — it is never blended into the same column as a DG-sourced SG stat.
- **Season baseline + recent form, both from Data Golf:** use `preds/skill-ratings` (DG's rolling baseline) as the season-equivalent input, blended with a computed **L30** window from `historical-raw-data/rounds` (confirmed: Brian's preference is 30 days, not 6 months). Formula:

```
Blended stat = (0.60 × DG skill-ratings baseline) + (0.40 × DG computed L30)
```

- Applies to SG: Approach, Putting, Around the Green, Off the Tee. Record the L30 date window pulled on the Model Weights sheet each week (e.g. "DG L30 window: Jun 18–Jul 17, 2026").
- Where a player has too few rounds in the L30 window to compute a reliable average, note it as unavailable — don't silently fall back to the baseline alone without flagging it.

---

## The L1 / L2 / L3 Model Structure

### L1 — Course Regression (composite fit score)
- Output: a single **L1 Score**, 0–100, percentile-based composite across the weighted stat categories for that course.
- Input factors, pulled automatically from Data Golf:
  - Blended APP/PUTT/ARG/OTT (skill-ratings baseline + computed L30, per above)
  - Banded proximity/GIR/rough-recovery from `approach-skill` where a course's profile calls for distance-specific analysis
  - Course-fit and course-history **components** from `preds/player-decompositions` (`cf_approach_comp`, `cf_short_comp`, `driving_accuracy_adjustment`, `driving_distance_adjustment`, `course_history_adjustment`, `course_experience_adjustment`, `major_adjustment` for majors)
  - Computed Birdie or Better % where a course's profile calls for it (from `historical-raw-data/rounds`)
- **Confirmed:** `player-decompositions` also returns DG's own `final_pred` (their complete pre-tournament prediction) — never use it wholesale as the L1 score, that would make StrokesEdge's "proprietary model" just a relabeled copy of Data Golf's own prediction. Use only the individual *component* adjustments as weighted inputs into StrokesEdge's own L1 formula, same as skill-ratings and approach-skill are used as inputs, not outputs.
- Weights are **course-specific**, not fixed — re-derived every week (see Weight-Setting below).
- Document the weight table and rationale for each weight on the Model Weights sheet every week.
- MDL PROB% (model-implied win probability) is derived from the L1 score distribution via softmax.

### L2 — Winner DNA Filters (hard gates)
- A small set of course-specific hard thresholds, calibrated to Data Golf's scale (see SG Methodology above).
- Every player gets **PASS** or **FAIL**. FAIL restricts a player to finish markets only (Top 10/20/Watch) and disqualifies them from outright/E-W and Longshot tiers — it doesn't drop them from the workbook.
- Gates are set per-course, documented with rationale on Model Weights (which historical winners/years support the threshold, sample size caveats).
- **Watch List carve-out:** players without enough PGA Tour ShotLink-equivalent sample (LIV/DP World players, or anyone Data Golf can't compute a reliable round-level SG split for) are never scored in L1/L2 — they go on the separate Watch List sheet with whatever raw odds/total-SG data is available, and a note explaining why they're excluded from regression.

### L3 — Value Screen (waits on odds — see Two-Stage Pipeline below)
- Restricted to L2 PASS players (plus near-passes worth flagging), sorted by **WIN EDGE** descending.
- `WIN EDGE = MDL PROB% − MKT PROB%`, where `MKT PROB% = 100 / (odds + 100)`, using live sportsbook odds from `betting-tools/outrights`.
- Positive edge = model thinks the market is underpricing the player; this is the pool the pick tiers draw from.
- Matchup tier pulls from `betting-tools/matchups` the same way, comparing DG's L1-rank-implied edge against the matchup line.

### Pick Tiers (output order, every week)
1. **E/W Winner** — 1–3 players, strong outright case
2. **Longshot / Value** — 1–2 players with a genuine statistical case and a large model-rank-to-price gap
3. **Top 10 / Top 20** — highest-confidence finish-market plays
4. **Matchup** — head-to-head or 3-ball plays where the model's rank gap disagrees with the market line
5. **Fade** — 2–3 overpriced names; must name the exact market being faded and state what remains valid

### Data rules (non-negotiable)
- Use only stats actually pulled. Never invent or estimate a missing number — mark it unavailable.
- Every pick cites the specific stat values that support it. Every fade names the exact market faded and what remains valid.
- No narrative betting, no recency bias, no gut feel — if a stat doesn't support a line, don't write it.
- Never mix a Data-Golf-scale stat with a PGA-Tour-scale gate threshold or vice versa (see SG Methodology).

---

## Automation & Scheduling

One Windows Task Scheduler task, mirroring `StrokesEdge Weekly Course Update`'s setup exactly:

- **Trigger:** Weekly, Monday, 6:00 AM, with Task Scheduler's built-in **"Repeat task every 3 hours, for a duration of 4 days"** (covers Monday 6am through Friday 6am). A single repeating trigger, not several separate scheduled tasks — see rationale below.
- **Action:** same shape as the existing task — `python.exe weekly_model_pipeline.py`, "Start in" the `weekly-model/` folder, "Run whether user is logged on or not."
- **Lock file** (`.weekly_model_pipeline.lock`, same atomic `O_CREAT | O_EXCL` pattern as `weekly_course_update.py`) so an overrunning firing can't overlap with the next one 3 hours later.
- **State file** per tournament (`weekly-model/[tournament-slug]/state.json`) tracks what's already been done this week — field pulled, weights proposed, weights approved, L1/L2 complete, odds live, L3/workbook complete — so every firing is idempotent: it checks state, does the next unblocked step, and exits. A firing that finds nothing new to do exits quietly without emailing.

### Why one repeating poll instead of guessing a Stage 1 trigger time
Rather than picking a fixed day/time for "the field is set" (real PGA Tour commitment deadline is Friday 5pm ET the week before, but Monday qualifiers and late alternates keep shifting a few names into Tuesday), Stage 1 just becomes the **first successful state-check**: the first Monday/Tuesday firing where `field-updates` returns a real field is when field pull + weight-proposal happens. No separate schedule needed — the same repeating trigger that polls for odds naturally also polls for field availability, a few hours at a time, starting Monday morning.

### Step sequence (what a firing does, based on current state)
1. **No field pulled yet →** pull `field-updates`, pull course/schedule context, compute structured course characteristics (course type, length, green profile, rough severity, primary defense, historical winner patterns, wind exposure) the same way `weekly_course_update.py` already researches course profiles. Call the Claude API (`ANTHROPIC_API_KEY`, same unattended pattern as `generate_analysis()`) to propose L1 weights and L2 gate thresholds with rationale. Write `weekly-model/[tournament-slug]/weights_proposal.md`, email Brian a summary (`send_email()`, same SMTP pattern), update state to `weights_proposed`, exit.
2. **Weights proposed, not yet approved →** check the proposal file's status line (see Weight Approval below). Still pending → exit, try again next firing.
3. **Weights approved, L1/L2 not run →** run regression using the (possibly Brian-edited) weights from the file, apply gates, write the Model Rankings sheet's data, update state to `l1l2_complete`, exit.
4. **L1/L2 done, odds not yet live →** query **every market the model actually consumes** — `betting-tools/outrights` for `win`, `top_5`, `top_10`, `top_20`, and `betting-tools/matchups` for `tournament_matchups` — not just one proxy market. (Whether these markets post simultaneously or staggered was not empirically confirmed this session — verifying it would require observing the actual moment a market flips from unposted to live, which didn't happen for any real event during this session. Checking every consumed market directly sidesteps needing that answer: it's correct whether they're simultaneous or staggered, at the cost of a few extra API calls, well inside the 45/min rate limit.) If any of them returns a placeholder ("no odds/matchups being offered") rather than real data, treat the whole check as not-ready, exit, try again next firing.
5. **Odds live, workbook not built →** pull `betting-tools/outrights` (all markets) and `betting-tools/matchups`, run L3 value screen, build all 7 Excel sheets, save the `.xlsx` locally to `weekly-model/[tournament-slug]/`, update state to `complete`, then **email Brian the finished workbook as an attachment** — same `send_email()` SMTP pattern as everything else, extended to attach a file (swap `MIMEText` for a `MIMEMultipart` with the `.xlsx` attached, same `GMAIL_APP_PASSWORD` credential). Chosen over a designated-folder handoff because it reuses the existing email pattern directly rather than adding a new mechanism, and Brian gets it immediately without having to go find a file. This pipeline's job ends here — it does not talk to the Apps Script sender (see note above).
6. **Already complete for this week →** exit immediately, no email.

### Escalation if odds never show up
If state is still stuck before step 5 by **Wednesday 6pm** (comfortably before Thursday tee times), send an explicit warning email ("odds still not live for [Tournament] as of Wednesday evening — may miss this week") rather than silently retrying into Friday. Matches `weekly_course_update.py`'s rule of always emailing on a notable state, never failing silently.

**Bug found and fixed during live testing:** the check is keyed purely off the tournament's calendar (`event["start_date"]`), with no awareness of whether the *current firing* just made real progress. A firing that writes a fresh proposal, or clears L1/L2, still evaluated "are we past Wednesday 6pm" and fired the warning in the same breath as the progress email — a guaranteed false alarm on any manual/out-of-band run, and a plausible one in real operation too (e.g. a firing that clears L1/L2 late Wednesday would escalate immediately after succeeding). Fixed in `process_event()`: escalation is now only evaluated on firings where `state["step"]` is unchanged from the start of that firing — real progress always suppresses the check for that firing, regardless of the wall-clock threshold.

---

## Weight Approval — File + Email, Not Interactive Chat

Since nobody is at a Claude Code session when this runs, the checkpoint from the earlier draft (Claude proposes weights inline, Brian replies in chat) doesn't work. Replaced with a file + email pattern:

1. Step 1 above writes `weekly-model/[tournament-slug]/weights_proposal.md` — a plain-text/Markdown file with a `STATUS: PENDING REVIEW` line at the top, the proposed weight table, gate thresholds, and Claude's rationale for each, in an editable format (not JSON — Brian should be able to open and edit this like the `weekly_course_update.log` file, no tooling required).
2. Emails Brian a **compact, readable summary of the proposed weights and rationale directly in the email body** — not just a link or a pointer telling him to go open the file. He should be able to gut-check the proposal from the email alone (weight table + one-line rationale per factor + gate thresholds), without opening the file every time. The file path and edit instructions (`STATUS: PENDING REVIEW` → `STATUS: APPROVED`) are included below that summary, for the times he does want to edit something.
3. Every subsequent firing (step 2 in the sequence above) checks the file's status line. Once it reads `APPROVED`, the pipeline proceeds using whatever weight values are currently in the file at that moment — so an edit made an hour before a poll fires gets picked up automatically, no separate "submit" action.

**Default behavior if Brian never responds: the pipeline waits indefinitely** (up to the Wednesday-evening escalation email above), it does not auto-approve on a timeout. This matches `weekly_course_update.py`'s `AUTO_PUSH = False` default — held for review is the safe default. If Brian decides later he wants a fallback (e.g. auto-approve after N hours if unreviewed), that should be a single clearly-marked config switch, off by default, same as `AUTO_PUSH` — not built now.

**Scope note:** this only supports editing the file directly (from Brian's own machine). It does not parse email replies (e.g. replying "approved" or "bump ARG to 18" from a phone) — that would need inbound IMAP polling plus free-text parsing into structured weight edits, meaningfully more complex and more fragile than a file-edit check. Flagged in Open Questions if that's actually needed.

---

## Concurrent Events — Multiple PGA Tour Tournaments in One Week

Real, current example confirmed this session (not hypothetical): `get-schedule?tour=pga` right now lists both **The Open Championship** and **Corales Puntacana Championship** with the identical `start_date` (2026-07-16) — a major/marquee event and its opposite-field companion running the same week, exactly the pattern Brian described (Scottish Open + ISCO Championship is the same shape). The pipeline handles any number of same-week PGA Tour events, not just one.

### Detection — no keyword guessing needed
Data Golf has its own tour taxonomy for this: `tour` accepts `pga`, `euro`, `kft`, `opp`, `alt`. **`opp` (opposite-field) is a distinct, queryable tour code** for exactly the alternate-field companion event that runs opposite a marquee week. Verified directly:
- `field-updates?tour=pga` → returned The Open Championship's field.
- `field-updates?tour=opp` → returned Corales Puntacana Championship's field, correctly isolated.
- `betting-tools/outrights?tour=opp&market=win` → returned Corales Puntacana's own odds, correctly isolated from the main event's.

Each firing queries `field-updates?tour=pga` (always — this is the main event) and `field-updates?tour=opp` (best-effort — succeeds only on weeks with a concurrent alternate-field event; on a normal single-event week this is expected to return an empty/error response, treated as "no concurrent event this week," not a failure). `get-schedule` itself does **not** accept `tour=opp` (tested, returns an error) — the schedule feed lists both events together under `pga`; it's `field-updates`/`betting-tools` specifically where `tour=opp` isolates the alternate event's own data.

Co-sanctioned Euro Tour weeks (e.g. Genesis Scottish Open) already appear under `tour=pga` in Data Golf's own schedule classification, same as majors — so the `pga`/`opp` split alone is expected to cover Brian's Scottish Open / ISCO Championship example without needing to separately query `tour=euro`. Not exhaustively tested against every co-sanctioned week; flagged in Open Questions.

### Main-event determination
No hardcoded keyword list (unlike `weekly_course_update.py`'s `MAJORS`/`ELEVATED_EVENTS`/`CO_SANCTIONED_KEYWORDS` — that logic lives in a different pipeline scraping a different source and isn't reused here). Instead: **the `tour=pga` event is the main/featured event by definition; the `tour=opp` event, when one exists, is the alternate/opposite-field event by definition.** This is Data Golf's own designation, not a guess.

This pipeline doesn't call or touch `weekly_course_update.py` or the site repo — but it makes the determination available and clearly logged, in case anything downstream (that separate site pipeline, or Brian manually) ever wants it: each event's `state.json` and `weights_proposal.md` carry an explicit `is_main_event: true|false` and `event_type: "featured"|"opposite_field"` field.

### Independent pipeline per event
Every concurrent event runs the full pipeline (field pull → weight proposal → approval → L1/L2 → odds check → L3 → workbook) completely independently:
- Separate state file: `weekly-model/[tournament-slug]/state.json`
- Separate weights proposal + approval email: `weekly-model/[tournament-slug]/weights_proposal.md`
- Separate final workbook, in its own subfolder: `weekly-model/[tournament-slug]/StrokesEdge_[TournamentSlug]_[Year]_MODEL.xlsx`
- Separate course-specific stats, L1 weights, and L2 gates — an opposite-field event's course/field profile has nothing to do with the marquee event's, so there's no shared state between them beyond both being detected in the same firing.

A single firing loops over every event detected that week (the `pga` event, plus the `opp` event if one exists) and advances each one's state machine independently within the same script run — no change to the single Task Scheduler task or the single lock file; the lock covers the whole firing (all events in that pass), not per-event.

### Naming
Tournament slug is derived from `event_name` the same way `weekly_course_update.py` slugifies course names — e.g. `the-open-championship` and `corales-puntacana-championship` as sibling folders under `weekly-model/`. Since the slug always includes the specific tournament name, filenames never collide within a shared week, satisfying the "never confuse two workbooks" requirement directly.

---

## Excel Template Format

Standard for every weekly workbook, matching `StrokesEdge_OpenChampionship2026_MODEL_FULL_Customer Copy (1).xlsx` — 7 sheets, in this order, every week regardless of event size (confirmed: not majors-only).

### 1. Cover
- Title block: `STROKESEDGE` / `[TOURNAMENT] [YEAR] · MODEL OUTPUT` / course, location, dates, par, yardage, field type.
- "TOP PICKS AT A GLANCE" table: `TIER | PLAYER | ODDS (BR) | MDL RK | EDGE | KEY REASON`.
- Separate `FADE` and `MATCHUPS` blocks below the main picks table.
- Full glossary block — every stat abbreviation, gate, and probability term gets one line explaining exactly what it is and how it's computed, course-specific values updated each week.

### 2. Dashboard
- Simple visual summary: `PLAYER | L1 SCORE` for the top ~15 players, sorted descending. Full detail lives in Model Rankings/Value Screen — this sheet is the at-a-glance view.

### 3. Picks Card
- Header: `STROKESEDGE — [TOURNAMENT] [YEAR] | PICKS CARD`, subhead with course/dates/win-place terms.
- Columns: `TIER | PLAYER | BET TYPE | ODDS (BR) | STAKE | MDL RK | EDGE% | VERDICT | RATIONALE | L2`.
- Rows ordered by tier per the Pick Tiers list above, including Matchup rows (`BET TYPE` = "Tournament NB" or similar, `MDL RK`/`EDGE%` = `—` where not applicable).
- `VERDICT` is `PLAY` or `FADE`. `L2` is `PASS`, `FAIL`, or `PASS*`/`FAIL*` (near-miss — explain which gate and by how much in the rationale).
- Footer disclaimer every sheet: "Not financial advice. Gamble responsibly. | strokesedge.com/picks.html | All picks logged to public tracker before first round."

### 4. Value Screen
- Header states sort order and gate summary inline (e.g. "L2 PASS players sorted by WIN EDGE descending · Gates: ...").
- Columns adapt to that week's actual weighted factors (course-specific, same as Model Rankings) but always include: `RK | MDL RK | PLAYER | L1 SCORE | MDL PROB% | MKT PROB% | WIN EDGE | WIN ODDS`, plus whichever stat columns are that week's L1 inputs.
- Include L2 PASS rows and near-pass FAIL rows (MDL RK ≤ 15), clearly distinguished.

### 5. Model Rankings
- Header includes the full weight string for the week and the data-source/window line, e.g. `Weights: APP 16% / Long-App 10% / ACC 16% / ... | SG Source: Data Golf skill-ratings baseline blended 60/40 with computed L30 | L2 PASS = clears all N Winner DNA gates`.
- Full field (excluding Watch List players), one row per player: `RK | PLAYER | DK SALARY` then all L1 input columns, then `L2 GATE`, `MDL PROB%`, `MKT PROB%`, `WIN EDGE`, and relevant market odds.
- `DK SALARY` sits immediately next to `PLAYER` (not off in a separate sheet) so a reader can cross-reference model score against DraftKings salary directly — sourced from `preds/fantasy-projection-defaults` (see endpoint table above), formatted `$X,XXX`. Shows `N/A` for a player with no DK salary this week (not yet released, or not on the DK slate) — never invented, per the Data rules below.
- This sheet is the audit trail — every number feeding the Picks Card, Value Screen, and the DFS article's salary board must be traceable here.

### 6. Watch List (LIV / DP World / insufficient sample)
- Header: `STROKESEDGE — [TOURNAMENT] [YEAR] | WATCH LIST (OUTSIDE REGRESSION)`.
- Columns: `PLAYER | WIN ODDS | TOP 20 ODDS | TOTAL SG | TOUR / STATUS | NOTE`.
- One row per player excluded from L1/L2 for insufficient sample, with the reason stated in `NOTE`.

### 7. Model Weights
- Header: `STROKESEDGE — [COURSE] [YEAR] | MODEL WEIGHTS, STAT SOURCES & L2 GATE REFERENCE`.
- Data-source line: exact Data Golf endpoints used, the computed L30 date window, and any PGA Tour CSV supplement added that week (or "none this week").
- Weight table: `STAT/CATEGORY | WEIGHT | SOURCE | RATIONALE | L2 GATE | GATE VALUE | PRIORITY` — one row per L1 factor, weights summing to 100%.
- "L2 WINNER DNA GATES" block below: one row per gate, threshold, and historical rationale.
- Footer: "Not financial advice. Gamble responsibly. | strokesedge.com/picks.html"

### General formatting rules
- File naming: `StrokesEdge_[TournamentSlug]_[Year]_MODEL.xlsx`.
- Every sheet gets its own title row and its own footer — don't rely on one disclaimer for the whole workbook.
- Numeric formatting: strokes-gained values to 3 decimals with explicit `+`/`-` sign; percentages to 1 decimal; odds as American odds with explicit `+` for positive.

---

## Resolved
- **Workbook handoff:** email the finished `.xlsx` to Brian as an attachment (not a designated folder) — reuses the existing `send_email()` pattern directly. No integration with the separate Google Apps Script sender.
- **PGA Tour CSV supplement:** checked automatically at firing time (field pull + again at regression); used if present, skipped (Data-Golf-only, noted on Model Weights) if absent.
- **Weight-approval fallback:** wait indefinitely, escalate Wednesday evening, never auto-approve. A week with no workbook because Brian was unreachable is an accepted outcome by design.
- **Approval channel:** file-edit-only, no email-reply parsing.
- **Polling cadence** (every 3 hours, Monday–Friday): accepted as a starting point, to be tuned after it's observed running against a real tournament week.
- **`player-decompositions` weighting:** use its component adjustments (`cf_approach_comp`, `cf_short_comp`, `driving_accuracy_adjustment`, `driving_distance_adjustment`, `course_history_adjustment`, `course_experience_adjustment`, `major_adjustment`) as weighted L1 inputs. Never use `final_pred`/`baseline_pred` wholesale — that would make StrokesEdge's model a relabeled copy of Data Golf's own prediction rather than a proprietary blend.
- **Odds-readiness check:** query every market the model consumes (win, top_5, top_10, top_20, tournament_matchups), not a single proxy market — sidesteps the unverified staggering question rather than assuming an answer.
- **Weight-approval email content:** full compact weights/rationale summary in the email body itself, not just a pointer to the file.
- **Concurrent events:** detected via `tour=pga` (main) + `tour=opp` (opposite-field, best-effort) on `field-updates`/`betting-tools`, each running the full pipeline completely independently with its own state/proposal/workbook, under its own `weekly-model/[tournament-slug]/` subfolder. Main-event status determined by Data Golf's own tour taxonomy, not keyword matching, and logged (`is_main_event`, `event_type`) for any future downstream consumer.
- **DK salary availability — resolved, was never actually a blocker:** `historical-dfs-data` (the endpoint this file originally pointed to) genuinely cannot provide current-week salaries — it's a completed-events-only feed, confirmed by testing it against the live 2026 3M Open (404, event not in that year's calendar yet) versus 2025's completed 3M Open (real data back). But a *different*, separate endpoint — `preds/fantasy-projection-defaults` — does provide real current-week DraftKings salaries, `dg_id`-keyed, confirmed live days ahead of a real tournament. No manual CSV/screenshot workaround was ever needed; the gap was in this file's original endpoint inventory, not in what Data Golf actually offers.
- **Par/yardage source of truth (2026-07-28):** `pgatour_course_par_yardage()` (pgatour.com's own `/course-stats` page, `courses[0].par`/`courses[0].yardage`) is now tried before the Wikipedia infobox fallback in both this pipeline and `weekly_course_update.py`, since it's the tour's current-year figure and reflects mid-year course changes (a renovation converting par-5s to par-4s, for example) that Wikipedia can lag behind. Found via a real case: Detroit Golf Club's 2026 restoration made Wikipedia's par/yardage stale.
- **Model Rankings sheet full-field bug (2026-07-28):** `build_workbook()`'s Model Rankings sheet was iterating the L2-PASS-only `ranked` list instead of the full scored field, silently dropping every L2 FAIL player from the sheet even though the design (see Excel Template Format below) says it should show the full field with PASS/FAIL noted per row. Not new to Rocket Classic — this affected every prior week's workbook (3M Open, Open Championship) the same way. Fixed: Model Rankings now iterates `full_field_ranked = sorted(l1_results.keys(), ...)`, all other sheets/tiers still use the PASS-only `ranked` list as designed.
- **Matchup VERDICT/L2 consistency (2026-07-28):** Picks Card matchup rows had a hardcoded `VERDICT = "PLAY"` regardless of either player's L2 gate status. Fixed: a matchup only shows `PLAY` if both players clear L2; otherwise `WATCH ONLY` with a rationale naming which player(s) failed. A standing validation loop at the end of `build_workbook()`'s Picks Card section now scans every data row and raises if any row has `VERDICT == "PLAY"` with `L2 == "FAIL"` — this is a general check (not matchup-specific) so any future tier added to Picks Card is covered automatically.
- **Course-change review flag (2026-07-28):** both `weekly_course_update.py`'s course-analysis prompt and this pipeline's `WEIGHT_PROPOSAL_PROMPT` now ask Claude for a `COURSE_CHANGE_FLAG: yes/no/uncertain` line (parsed out and stripped before publishing/use). When `yes` or `uncertain`, it's surfaced prominently — a `!! COURSE CHANGE FLAG !!` block in `weights_proposal.md` and the proposal email, a `[COURSE CHANGE]` email subject prefix on both pipelines' emails, same convention as the existing `[ZEROED FACTOR]` flag. Advisory only, doesn't block approval — the point is making a material course change (restoration, redesign, hole conversions) impossible to miss on a skim, not auto-adjusting weights. Added after the Detroit Golf Club restoration almost got missed this week (see Course-Specific Weight Baselines below).
- **Article SEO structure (2026-07-28):** every picks article and DFS article now opens with a code-templated lead sentence naming the tournament, year, and course (`render_faq_section`'s sibling lead-sentence logic in `generate_substack_article`/`generate_dfs_article` — not left to the Claude-written intro to remember) and closes with a code-templated `## FAQ` section (`render_faq_section()`, 3-5 Q&A pairs: when/where the tournament is, StrokesEdge's top pick, plus one article-specific pair). Fully code-assembled from data already computed that run, not a Claude call, so it can't drift or time out.

### Course-Specific Weight Baselines

Standing reference for courses with a known reason to deviate from a fresh-generated proposal — check here before approving a new week's auto-generated weights for these courses, since a from-scratch Claude proposal has no memory of this.

- **Detroit Golf Club / Rocket Classic (set 2026-07-28, Brian-approved):** the course underwent a $16.1M restoration completed in 2026 (greens rebuilt to Ross's original shapes, holes 7 and 17 converted from par-5s to long par-4s at 505/537 yards, pond on 14 filled in) — functionally a new course. `course_history_adjustment` and `course_experience_adjustment` were cut from the fresh-proposal defaults of 4%/3% to **2%/1%**, with the 4 points reallocated to `sg_app_blend` (18% → 20%) and `sg_arg_blend` (11% → 13%). Use these as the starting weights for Rocket Classic at Detroit Golf Club in future years too, not just this one — re-derive from scratch only if the course changes materially again or enough post-restoration history accumulates that course history becomes meaningful again.

## DFS Article — DraftKings Lineups From the Same Model Data

Every firing that builds the workbook + picks article now also attempts a DFS article, using the exact same `metrics`/`l1_results`/`l2_results`/`l3` the picks article and workbook use — no separate data pull beyond the one extra call to `preds/fantasy-projection-defaults` (see endpoint table above). Same design discipline as the picks article: every number (salary, DK value, ownership, lineup composition, edge%) comes from code; Claude writes only the connective narrative prose, given the real computed numbers as context.

**Structure** (matched against a real published StrokesEdge DFS piece, not guessed): `01 Slate Setup` / `02 GPP Lineup` / `03 Cash Lineup` / `04 The Chalk Problem` / `05 Weather Note for DFS Builders` / `06 Full Salary Board Reference` — same section-numbering convention as the picks article.

**Lineup construction** — DraftKings PGA classic rules: $50,000 cap, 6 golfers, no position requirements (`DFS_SALARY_CAP` / `DFS_ROSTER_SIZE` in the script). Both lineups are built with an exact 0/1 knapsack (`_knapsack_lineup()`, bucketed to $100 salary steps — cheap at ~150 candidates × 6 slots × 500 buckets), not a greedy top-N, so the cap is never accidentally busted and real salary isn't left on the table when the objective calls for using it:
- **GPP** maximizes total **L1 score** across the *full field*, not gated by L2 PASS — leverage means favoring players the model likes that DK's market hasn't priced up yet, which is a different question from "will this player win outright" (that's what L2's Winner DNA gates measure). A GPP lineup can and will include L2 FAIL players; the `render_dfs_lineup_table()` model-rank column shows `#—` for those, same convention already used for FADE-tier rows elsewhere in the workbook.
- **Cash** maximizes total DK `value` (points per $1,000 salary) restricted to **L2 PASS players only** — floor/consistency over spike upside, matching the real reference article's own stated cash-build rule ("the six highest DK-value scores... that also clear the model's L2 gate").
- Either lineup renders as `*Not enough eligible players this week to build this lineup.*` rather than a fabricated partial lineup if fewer than 6 eligible candidates exist — never invent a 7th or 5th-golfer workaround.

**Delivery** — attached to the same email as the workbook and picks article, via the same `send_email(attachment_paths=[...])` call, from a new shared `_build_and_deliver()` function that both the normal step machine and `--rebuild` (see below) call — so a real weekly firing and a manual rebuild can never drift into producing different sets of deliverables. If DK salaries aren't released yet at the moment odds go live (in practice this hasn't been observed — DK salaries were already live well before matchup odds posted, in the one real week tested), the DFS article is silently skipped for that firing (logged, noted in the email body) rather than delaying the workbook/picks article, which are the primary deliverable and must not wait on a DFS-specific dependency.

**Manual rebuild (`--rebuild SLUG`)** — added specifically to backfill a deliverable (like the DFS article) into a week whose state already reached `complete` without it, without re-running the whole approval/regression pipeline. Bypasses the step machine, loads the event fresh from `detect_events_this_week()` (so course/location/lat-lon are current, not stale) and the saved `metrics`/`l1_results`/`l2_results`/`weights`/`gates` from `state.json`, re-checks that outright odds are still live (aborts if not — WIN EDGE can't be recomputed without them), and calls `_build_and_deliver()` directly. Only works while Data Golf still lists the event as upcoming (i.e., before/during tournament week) — there's no path to rebuild for an event that's already been played and dropped off the schedule feed.

## StrokesEdge Article Title Format

Always use this exact structure for weekly tournament articles (picks/substack and DFS — not the recap article below, which uses its own past-tense title convention):

Substack/betting article:
`[Tournament Name] [Year] Picks: Model Best Bets and Fades for [Full Course Name]`

DFS article:
`[Tournament Name] [Year] DFS Picks: Best DraftKings Lineups for [Full Course Name]`

Example: "BMW Championship 2026 Picks: Model Best Bets and Fades for Bellerive Country Club"

Use the full official course name every time. This format is proven to drive Google search traffic and must not be changed.

**Enforced in code, not left to the model to remember** (Brian, 2026-08-18): `generate_substack_article()` and `generate_dfs_article()` in `weekly_model_pipeline.py` build the title directly from `event['event_name']`, the year, and `event['course_name']` — the same "code-templated, can't drift" discipline as the lead sentence and FAQ section. Previously the picks article title used a Claude-generated `TITLE_HOOK` phrase (removed from the narrative prompt entirely, since nothing else used it) — that was a real gap, since a model-written hook could vary the exact title structure week to week even though everything else about the format was already fixed.

## Recap Article — Post-Tournament FedEx Cup / Results Recap

A separate weekly deliverable from the picks and DFS articles: instead of previewing the upcoming field, it looks back at the tournament that just finished. First built manually 2026-08-18 for the FedEx St. Jude Championship (`fedex-st-jude-championship/recap_article_FedexStJudeChampionship_2026.md`) — use that file as the reference example for structure and tone until a second real week confirms the pattern holds.

**Not part of `weekly_model_pipeline.py`.** The picks/DFS articles are deterministic-data-plus-narration (every number comes from code, Claude only writes connective prose) because Data Golf supplies every input pre-tournament. The recap needs two things Data Golf's API doesn't confirm-available: the tournament's actual final leaderboard and the FedEx Cup points standings after it. Both are sourced by live web search each run, not a typed API call — this is a research-and-write task, not a regression pipeline, so it runs as a scheduled Claude Code agent (see Automation below), not a Task Scheduler Python job.

**Trigger:** every completed PGA Tour event that has a `substack_article_*` but no `recap_article_*` yet, not just the most recent one. Processed **oldest first** — a week the routine missed (network blocker, Brian skipped a Monday, etc.) stays queued rather than getting silently skipped forever once a newer tournament finishes. During the FedEx Cup Playoffs specifically (St. Jude → BMW → Tour Championship) every event in the backlog is a Playoffs event.

**Data sources, in order:**
1. `weekly-model/[tournament-slug]/substack_article_*.md` from that same tournament's preview — this is what tells you which players StrokesEdge actually had picks on and why, so the recap can grade the model's own reasoning rather than just restating final scores.
2. The pick tracker CSV (see Pick Tracker Data above, same URL) — pull every row for that tournament and tally the record (bets, W-L, total wagered, total payout, net, ROI) **in code/arithmetic, not from memory or estimation** — same "never let an LLM's arithmetic be the record" discipline as `shared/tracker.py`'s `summarize_final_results()` in the Twitter pipeline. Cross-check every bet's `result` column against the actual final leaderboard position before writing a line about it.
3. Web search (at least one sports-media source, e.g. CBS Sports/PGA Tour leaderboard pages) for the final leaderboard: winner, score, margin, and enough of the top finishers to cover every player StrokesEdge had a bet on.
4. Web search for FedEx Cup points standings after the event, and for the next Playoffs event's course/dates/field-size, during Playoffs weeks specifically. **Open question, same caveat as the Open Questions list below:** no Data Golf endpoint for FedEx Cup point totals has been confirmed — this is sourced from web search every time and should be cross-checked against a second source when the numbers matter (e.g. the leader's point cushion), same bar as the par/yardage cross-check rule in the site's `CLAUDE.md`.

**Structure** (matched against the FedEx St. Jude recap, adjust section count for non-Playoffs weeks that don't need a standings section):
`01 Final Leaderboard` (table, enough rows to cover every player StrokesEdge picked) / `02 How the Model's Picks Actually Played` (grade each pick against what the model's own rationale said, not just win/lose — the FADE vs Top-10/20 distinction on the week's biggest name is exactly the kind of thing worth calling out when the model got the *shape* of a call right even if a bet on that player lost) / Tracker Record table (bet type broken out, not just one aggregate line) / `03 FedEx Cup Standings` (Playoffs weeks only) / `04 Looking Ahead` (next event's course/dates, teases that week's upcoming picks article) / `## FAQ` (`render_faq_section`-style, 3-5 Q&A: who won, how did StrokesEdge do, standings snapshot, next event logistics).

Opens with the code-templated lead-sentence convention (tournament, year, course, but past tense since it's a recap) and closes with the same footer block as the picks article (full record link, workbook/membership plug, "Not financial advice. Gamble responsibly.").

**File naming:** `recap_article_[TournamentSlug]_[Year].md`, same folder as that week's `substack_article_*`/`dfs_article_*`.

**Data rules:** same as the rest of this pipeline — never invent a leaderboard position, standings number, or tracker result. If the tracker CSV shows no bets logged for a tournament, say so plainly rather than skipping the section.

### Automation — Monday 9:00 AM

Runs as a scheduled Claude Code cloud routine (not `weekly_model_pipeline.py` / Task Scheduler — see rationale above), weekly, Monday 9:00 AM ET. Deliberately the morning after, not Sunday night: the tracker CSV's `result` column for that week's bets is filled in by Brian by hand (not automatically settled), so the run is timed to land after he's had Sunday evening to update it, not immediately after final rounds finish. Running before he updates it would mean grading picks against a still-`open` tracker, silently wrong. The routine:
1. Builds the full backlog: every tournament-slug folder under `weekly-model/` with a `substack_article_*` but no `recap_article_*` yet, sorted **oldest first** by the tournament's date.
2. Fetches the pick tracker CSV **once** for the whole run, not once per tournament — same source data, just filtered differently per tournament in the loop below.
3. For each tournament in the backlog, oldest first: follows the Data sources and Structure steps above (using the already-fetched tracker CSV, filtered to that tournament's rows), writes `recap_article_[TournamentSlug]_[Year].md` into that tournament's folder, then commits **only that one file** to its own new branch (e.g. `recap-[tournament-slug]-[year]`) and opens its own separate pull request titled `Recap: [Tournament] [Year]` — one PR per tournament, never a combined PR bundling multiple weeks, so Brian can review and merge each independently. **Unlike the local Task Scheduler jobs elsewhere in this pipeline, this routine runs in an ephemeral cloud sandbox with its own git checkout — nothing persists unless it's committed**, which is why every tournament gets pushed immediately after its file is written rather than held until the end of the loop.
4. If one tournament in the backlog can't be completed (its final leaderboard isn't confirmable from a live source, e.g. an event still in progress or postponed), skip just that tournament — no commit, no PR, noted in the final summary — and continue on to the next one in the backlog rather than aborting the whole run. If the tracker CSV fetch itself fails in step 2, the whole run is blocked (every tournament needs it) — skip the entire backlog and say why, same as before.

Brian merges each PR as it comes in, then publishes to Substack manually. The routine never posts anywhere else and never touches the deployed site pages (`Strokes Edge Website HTML/`) — same "hold for review, human sends" posture as the rest of this pipeline, just implemented as a PR instead of a local held file, since there's no local disk to hold one on.

## Open Questions
1. **`tour=opp` absence ≠ confirmed "no alt event"** — a failed/empty response from `tour=opp` is being treated as "no concurrent alternate event this week," but that's indistinguishable from a transient API issue without more observation. Worth logging the raw response for the first several real weeks to sanity-check this assumption before trusting it silently.
2. **Co-sanctioned Euro Tour weeks** — reasoned (not exhaustively tested) that `tour=pga` already captures co-sanctioned events like Genesis Scottish Open, so the `pga`/`opp` split alone should cover Brian's example. Worth confirming against a real Scottish-Open-type week once one comes up.
3. **Odds-market simultaneity** — genuinely unresolved (would require observing a live pre-to-post transition, which didn't happen this session). Mitigated by checking every consumed market rather than one proxy, so this shouldn't block building, but flagged as an assumption, not a confirmed fact.

## Post-Build: Validated, Compared, and Extended

`weekly_model_pipeline.py` is built and has run a real end-to-end cycle (field → Claude weight proposal → file approval → L1/L2 → odds check → L3 → workbook → email), confirmed delivered to strokesedge@gmail.com. Since the initial build:

- **5-tournament backtest** (`backtest.py`, `temperature_analysis.py`) against real 2026 results, letting weights vary naturally per course, found the general scoring machinery sound (mean Spearman ρ +0.352 between L1 score and actual finish, positive in all 5 events) but the softmax temperature miscalibrated (fixed T=8 gave implausibly high top-pick probabilities, 17% mean). Fixed: `SOFTMAX_TEMPERATURE_MULTIPLIER` now scales adaptively to each week's own L1 score spread (`T = 1.0 × stdev(L1 scores)`) instead of a fixed constant — verified this only changes probability magnitude, not rank order.
- **4-tournament weight comparison** against real historical customer-copy workbooks (ISCO, John Deere, Open Championship, Scottish Open) found generally sound directional judgment (5 exact weight matches, consistent top-2/3 category agreement) but one repeat failure mode: SG:Off-the-Tee zeroed out entirely in 2 of 4 fresh proposals where the historical model gave it real weight. Also found real catalog gaps: par-3/par-4-5 scoring splits, GIR%, and Scrambling% weren't available as factors.
- **Zeroed-core-factor safeguard added**: `detect_zeroed_core_factors()` flags (in both the file and the email, with a `[ZEROED FACTOR]` subject prefix) whenever any of the four universal SG categories (APP/PUTT/ARG/OTT) is absent from a proposal — advisory only, doesn't block approval, makes the miss impossible to skim past.
- **FACTOR_CATALOG extended** with `gir_pct` and `scrambling_pct` (both computed from `historical-raw-data/rounds`, same L30-window pattern as `bob_pct`). Par-3/Par-4-5 scoring average confirmed **not computable from any Data Golf endpoint** — checked both `historical-raw-data/rounds` (round-level totals only, no per-hole data) and `historical-event-data/events` (points/earnings/finish only); the only hole-level endpoint (`preds/live-hole-stats`) is live/in-tournament only. Permanent structural gap — would need a PGA Tour CSV to ever get these two stats, same as the historical Scottish Open workbook actually sourced them.
- **Brand styling applied** to the real workbook output — colors and fonts read directly off actual customer-copy files (not approximated): `COLOR_BG_DARK` #080B07, `COLOR_HEADER_GREEN` #6AB83A, `COLOR_SECTION_FILL` #1C3A14, `COLOR_DATA_FILL` #D5E8D4, `COLOR_DATA_TEXT` #1C3A14, `COLOR_HIGHLIGHT_GREEN` #1C6B22 (key numeric values), `COLOR_FADE_RED` #C0392B (FADE verdict specifically), Calibri throughout. Two matplotlib charts (Top 15 L1 Score, Model vs Market Edge in green/red) embedded on the Dashboard sheet — note the real reference file actually used native Excel charts with a single solid color, not raster images with a green/red split; built as explicitly instructed rather than as literally observed. Hit and fixed a real matplotlib bug along the way: forcing Calibri onto chart tick-label text (vs. the title, which was fine) rendered blank on this system — tick labels use the default font instead, spreadsheet cell fonts are unaffected.

Brian is running one full week manually (not yet via Task Scheduler) to personally review the weight proposal and final workbook before deciding to schedule it unattended.

## Live-Run Bugs Found and Fixed (The Open Championship manual test)

- **Escalation false alarm**: fixed as described above under "Escalation if odds never show up" — the check now skips any firing that made real progress, rather than firing based purely on the tournament's calendar date.
- **Precision-loss bug on small-magnitude factors**: `CF_APPROACH_COMP` displayed as exactly 0.000 for every player in the field — looked like a broken/dead factor. Root cause: `FACTOR_CATALOG` spans wildly different natural scales (`cf_approach_comp` ~1e-4, `cf_short_comp` ~1e-2, SG blends ~1e0, rate stats ~1e1), and a single fixed `round(v, 3)` / `:+.3f` used everywhere destroyed real signal on any factor whose natural magnitude is smaller than 0.001 — not a display quirk, the value was actually zeroed before reaching the cell. Confirmed live: 156 real, distinct `cf_approach_comp` values (range -0.000127 to +0.000203) all rounding to zero under the old rule. Also silently affected `driving_accuracy_adjustment` for players with small values — caught by the same fix, discovered only because Brian's own weight edit that same session raised that factor to 15%. Fixed with `_round_factor_value()`/`_fmt_factor_value()` — adaptive precision (~3 significant figures) instead of a fixed decimal count, applied everywhere a raw factor value is shown (Value Screen, Model Rankings, Picks Card/Cover rationale text, L2 gate detail strings). The underlying L1 percentile scoring was never affected by this bug — it always used the unrounded value; only display columns were broken.
- Note for anyone auditing old test output: the workbook emailed at 2026-07-18T18:07 UTC has the broken zeroed column; the one at 18:36 UTC has the fix. Don't trust the earlier one.

### Substack article — quality bugs found and fixed (same manual test)

- **Missing FADE/MATCHUPS sections**: both were silently omitted whenever their tier list was empty (`if tiers["fade"]:` / `if tiers["matchup"]:`), which every published article requires as standing sections. Diagnosed against live data: `matchups_ready` was genuinely `False` (odds never posted that week — real, not a bug) and the fade tier had zero qualifying players (mechanical consequence of the stale in-progress-tournament test data, not a fade-logic bug). Fixed the structural issue regardless: both sections (workbook Cover sheet and article) now always render their header, with explicit fallback text when empty ("No L2-fail short favorites... identified this week." / "Matchup odds were never posted this week.").
- **Templated, duplicated player prose**: `player_rationale()` (built for scannable workbook cells) was being reused for article prose, producing near-identical sentence structure per player and verbatim-duplicate text between the Top Model Outputs and Full Picks Card sections for the same player. Replaced with `generate_pick_writeups()` — one Claude call producing genuinely varied prose per player from real citation data (including a computed `field_best` flag so superlative claims are verifiable, never invented), split into a LONG (deep-dive) and SHORT (compact list) version specifically so the two article sections never repeat the same sentence for the same player.
- **Truncated writeups, in two stages**:
  1. First failure mode: `max_tokens=4000` on the pick-writeup call was sized for the visible text output alone, but this model's `thinking` content block draws from the *same* budget — one real call finished cleanly (1404 thinking + ~2000 text tokens for 11 players), another identical-prompt call burned far more into thinking (non-deterministic) and cut text off mid-word after ~4 players. Root-caused by reading the raw truncated output tail directly. Fixed by raising to 8000, and separately hardened the parser from one combined ID/LONG/SHORT regex to a two-stage parse (find `ID: N` boundaries first, extract LONG/SHORT within each isolated block) so one malformed player can't cascade into breaking every subsequent player.
  2. Second failure mode, found via full-article re-read after the first fix: even at `max_tokens=8000`, one real run truncated mid-sentence on the *last* player only (Mitchell, Keith's SHORT field ended "...and there" with nothing after) — thinking-token consumption is per-call non-deterministic, so 8000 wasn't always enough margin. This slipped through undetected because the old parser's SHORT regex (`SHORT:\s*(.+?)\Z`) matches to end-of-string, so a cut-off fragment still counted as "found." Fixed three ways: `max_tokens` raised to 12000 for real headroom; the API's `stop_reason` is now checked and a `"max_tokens"` result discards the whole response and retries rather than parsing a response known to be incomplete; and every parsed LONG/SHORT field is now validated to end in terminal punctuation (`_looks_complete()`) before being accepted — a field that looks "found" but was actually cut off is now treated as missing, so the existing retry/fallback path actually engages instead of silently shipping broken prose.

Article verified clean after all fixes: no fallback text, FADE/MATCHUPS present with correct messaging, Top Model Outputs and Full Picks Card sections use genuinely distinct wording per player, and prose structure varies player to player.

Otherwise ready to move to implementation.
