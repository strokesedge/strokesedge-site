# Archived — superseded 2026-07-31

This was the original single-pipeline prototype: one generator that branched
on tournament phase (early_week vs picks) and routed output into a shared
approve/reject queue. It was never wired to Task Scheduler and never posted
anything for real (no posted_log.jsonl was ever created — check queue/ here,
everything in it is test data from generator dry-runs on 2026-07-30).

Replaced by two structurally independent pipelines per Brian's 2026-07-31
request — see `../stream1_auto/` (automatic, no-link, no human review) and
`../stream2_manual/` (drafted with links, emailed to Brian, no auto-post).
Kept here for reference only. Do not run these scripts against the real X
API or Gmail account — they duplicate functionality the new streams own.
