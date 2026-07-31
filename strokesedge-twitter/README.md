# StrokesEdge Twitter — Two Independent Streams

This folder runs **two structurally separate pipelines**. They share only
pure utility code (`shared/`) — no queue, no routing, no approval flow, no
config crosses between them. Built 2026-07-31, replacing the earlier
single-pipeline prototype (kept for reference in `legacy_v1/`, never wired
to Task Scheduler, never posted anything for real).

## Stream 1 — `stream1_auto/` — fully automatic, no links

- Posts standalone tweets (never replies) via the X API on its own. No
  human ever reviews these before they post.
- Categories: course facts/analytics, model methodology, general
  course-fit commentary, weather notes, and post-tournament recaps.
  Recap only runs Sunday evening through Monday, and only once the
  tracker CSV shows every bet for the tournament settled (won/lost/
  placed, none still "open") — it states the exact final record from
  that CSV, nothing guessed. Wed-Sat never gets recap or any in-progress
  standing content, because there's no live leaderboard data source wired
  in — see "Known gap" below.
- **Never** includes a link or URL. Can say "StrokesEdge" as plain text,
  just never as a link. `post_tweets.py` hard-checks for
  `strokesedge.com` / `picks.html` immediately before every API call —
  this is a re-check, not the only check; `generator.py`'s automated
  safety net (there's no human review, so this stands in for one) already
  discards anything with a link, betting language, in-progress standing
  language, or over 280 characters before it ever reaches `post_tweets.py`.
- ~15 posts/day, spread across a 7am-11pm active window (64-minute
  cadence). Costs $0.015/post (no-link API rate). Self-imposed monthly
  budget ceiling in `config.py` (`MONTHLY_AUTO_POST_BUDGET`) — not a real
  X cap, just a guard against a scheduling bug running up a bill
  unattended.

## Stream 2 — `stream2_manual/` — drafted, with links, for Brian to post

- Never touches `post_tweets.py`, never calls the X API, costs nothing.
- Same base categories as Stream 1, plus a `picks` category once the
  tracker CSV shows open bets for the current tournament — sourced ONLY
  from that CSV, never from `analysis.html`, once picks are live.
- Every slot generates 2-3 different phrasings of the same underlying
  tweet, all including the `picks.html` link, so Brian picks one instead
  of editing from scratch.
- **No approval step.** Each batch emails straight to
  strokesedge@gmail.com the moment it's generated, subject line
  `MANUAL POST — pick one, copy, paste (...)`, with all options shown
  together. Brian copies the one he likes into X himself.
- ~10 batches/day, delivered as they're generated rather than one daily
  digest. 90-minute cadence across the same 7am-11pm window (16h/90min ≈
  10-11 batches — a cleaner number than the exact 96-minute division of
  16h/10, landing on the same "~10/day").

## `shared/`

Pure utilities only, reused by both streams to avoid the two definitions
drifting apart on something safety-critical:
- `tournament_config.py` — the current live tournament. One fact both
  streams need to agree on; edit this weekly.
- `tracker.py` — tracker CSV fetch, `is_picks_phase()`,
  `is_tournament_complete()`, `summarize_final_results()` (deterministic
  won/placed/lost tally, computed in code so a recap's "3-for-8" is never
  an LLM arithmetic mistake).
- `claude_api.py` — thin Claude API wrapper.
- `email_utils.py` — thin Gmail SMTP wrapper.
- `html_utils.py` — HTML-to-text + local site-file loading.
- `link_check.py` — single definition of "does this text contain the
  site link," since Stream 1 must never have one and Stream 2 must
  always have one.

Neither stream imports the other's `config.py`, `content.py`,
`generator.py`, or queue files.

## One-time setup

```
pip install tweepy --break-system-packages
```

Environment variables needed (Windows, `setx VAR "value"`, restart
terminal after): `ANTHROPIC_API_KEY`, `GMAIL_APP_PASSWORD`, `X_API_KEY`,
`X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`. Same variables
as before — nothing new to provision.

Confirm `shared/tournament_config.py` points at the right tournament
before testing.

## Testing (do this before wiring up Task Scheduler)

**Stream 1** (from `stream1_auto/`):
```
python generator.py              # one generation + safety-check, no posting
python run_cycle.py --force --dry-run   # full cycle, prints what it would post
python run_cycle.py --force             # full cycle, REAL post to X
```

**Stream 2** (from `stream2_manual/`):
```
python generator.py              # one batch of 2-3 options, prints them, no email
python run_cycle.py --force      # full cycle, REAL email to strokesedge@gmail.com
```

Run the real (non-dry-run) commands deliberately a few times each before
scheduling anything, same as before — confirm a real post lands correctly
on X and a real email actually arrives.

## Task Scheduler setup

Four independent scheduled tasks (not two — generation and posting are
separate concerns even though Stream 1 does both in one script call):

| Task | Command | Working dir | Frequency |
|---|---|---|---|
| Stream 1 cycle | `python run_cycle.py` | `stream1_auto/` | every 15 min, always |
| Stream 2 cycle | `python run_cycle.py` | `stream2_manual/` | every 15 min, always |

Each script decides for itself whether it's actually time to act (active
hours + cadence, persisted in its own `queue/generate_schedule_state.json`)
— the 15-minute trigger is just a tick, not the real schedule. This is the
same pattern the legacy prototype used, just split two ways instead of one.

## Known gap — flag if you want this scoped out

There's no real-time leaderboard data source wired in anywhere in this
system. Stream 1's Wed-Sat content deliberately stays in the "here's the
model, here's the course" lane rather than reporting live standings, and
recap only fires once the tracker CSV shows a tournament fully settled.
If you want Thu-Sun content to reference actual live position, that needs
a leaderboard API integration scoped separately — say the word and I'll
put together options.

## Safety notes (do not remove without a good reason)

- Stream 1: `generator.py`'s safety-net checks (link, length, betting
  language, in-progress standing language) run on EVERY generated tweet
  before `post_tweets.py` ever sees it, because nothing else reviews this
  stream. `post_tweets.py` re-checks the link anyway as the final gate
  before the irreversible public API call.
- Stream 2: every option that's missing the link or over 280 characters
  is silently filtered out before the email goes out — Brian never sees
  an unusable option, he just sees fewer of them.
- `shared/tracker.py` fails safe (no picks content, no recap, no
  "tournament complete") on any CSV fetch error, rather than guessing.
- Both streams' category rotation falls back to the next available
  category if the intended one has no usable source content this run
  (e.g. "weather" with no forecast added to the page this week) — the
  model is never asked to fill a content gap with invented facts.
