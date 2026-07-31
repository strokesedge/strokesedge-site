# StrokesEdge Twitter Auto-Poster — Setup Guide

## What this does
1. `queue_manager.py` checks the tracker CSV to see if picks are live for the
   current tournament (`config.py`). If not, it generates early-week tweets
   from `analysis.html` (+ course file if one exists). If picks ARE live, it
   pulls player/odds ONLY from the tracker CSV — never from analysis.html.
2. Early-week tweets auto-approve into `queue/approved_queue.jsonl`.
   Anything mentioning picks, odds, or tiers ALWAYS goes to
   `queue/pending_review.jsonl` and triggers an email to strokesedge@gmail.com.
3. Brian approves pending tweets with `approve.py`.
4. `post_tweets.py` posts everything in `approved_queue.jsonl` to X, then logs
   it to `posted_log.jsonl` so nothing posts twice.

## One-time setup (do this in Claude Code)

1. Copy this whole `strokesedge-twitter` folder into
   `C:\Users\bkopp\strokesedge-site\` (or a subfolder there).

2. Install dependencies:
   ```
   pip install tweepy --break-system-packages
   ```
   (`ANTHROPIC_API_KEY` calls use only the standard library, no extra install needed.)

3. Set these Windows environment variables (in addition to the existing
   `ANTHROPIC_API_KEY` and `GMAIL_APP_PASSWORD`):
   ```
   X_API_KEY               <- Consumer Key / API Key from X developer console
   X_API_SECRET            <- Consumer Secret / API Key Secret
   X_ACCESS_TOKEN          <- Access Token (must show "Read and write")
   X_ACCESS_TOKEN_SECRET   <- Access Token Secret
   ```
   Set via: System Properties > Environment Variables, or in Command Prompt:
   ```
   setx X_API_KEY "your_key_here"
   setx X_API_SECRET "your_secret_here"
   setx X_ACCESS_TOKEN "your_token_here"
   setx X_ACCESS_TOKEN_SECRET "your_token_secret_here"
   ```
   Restart the terminal after running `setx` for the values to take effect.

4. Confirm `config.py` points at the right tournament. Right now it's set to
   test against **The Open** (uses `analysis.html` only, no course file).
   Next week, update it to 3M Open once that analysis file exists.

## Testing it (do this first, before scheduling anything)

```
cd strokesedge-twitter

# Step 1: see what phase it thinks we're in and what it would generate
python generator.py

# Step 2: run the real queue manager (writes to queue/ files, sends email if needed)
python queue_manager.py

# Step 3: check what's pending
python approve.py

# Step 4: approve one (example: approve item #1)
python approve.py 1

# Step 5: DRY RUN posting — prints what it would post, does NOT actually post
python post_tweets.py --dry-run

# Step 6: when ready for real, actually post
python post_tweets.py
```

Run steps 5 and 6 separately and deliberately at first — don't wire up
Task Scheduler until you've confirmed a real post lands correctly on X.

## Once confirmed working, set up Task Scheduler

Two separate scheduled tasks:
- **Generate**: `python queue_manager.py` — run once or twice daily during
  tournament week (e.g. 8am and 2pm).
- **Post**: `python post_tweets.py` — run daily, ideally a few hours AFTER
  the generate task, so there's a window for Brian to review/approve.

## Safety notes (do not remove these without a good reason)
- `needs_review()` in `generator.py` forces human review for ANY tweet
  generated during picks phase, no exceptions — plus a keyword safety net
  (odds, unit, fade, etc.) for early-week tweets that accidentally drift
  into pick-like language.
- `tracker.py` fails safe to "early week" mode if the CSV can't be reached,
  rather than guessing.
- Every generated tweet is checked against the 280-character hard limit as
  part of the system prompt — but worth spot-checking `char_count` in the
  jsonl files before approving, in case the model miscounts.
