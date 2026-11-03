"""
Shared tone/SEO rules for every tweet prompt. One definition so Stream 1,
Stream 2 and the live-standings prompts can't drift apart. Added 2026-10-30
at Brian's request: positive, SEO-minded tweets that build search traction
for strokesedge.com and the weekly Substack picks article.

Positivity never overrides accuracy: it changes WHICH true facts lead and
HOW they are framed, never the facts themselves.
"""

POSITIVE_TONE_RULES = """POSITIVE TONE (required):
- Upbeat, confident and encouraging. Lead with the strongest TRUE thing in
  the source content (the best-placed pick, a good round, a clean model
  fit) and keep the overall feel optimistic.
- Never invent good news. If the source shows a pick struggling or a
  missed cut, do not spotlight it: lead with a pick that is doing well, or
  write about the model and course instead. Never spin a bad position into
  a false one ("still in the mix", "right there" only when the source
  numbers actually show it).
- No negativity about players, other analysts or the field. Fades are
  framed as "model prefers other options this week", never as a pan.
- No hype words like "lock", "guaranteed", "can't miss"."""

SEO_RULES_LINK_FREE = """SEO (search traction for StrokesEdge, link-free stream):
- Name the tournament in full and the course naturally,
  and use the weekly hashtag when it fits.
- Use natural search phrases a golf fan would type (e.g. "{tournament} picks",
  "{tournament} course fit", "model") where the content allows it, and
  write "StrokesEdge" in plain text so the brand name gets searched.
- Hashtag: use ONLY the exact weekly hashtag {hashtag}. Never shorten it or invent other hashtags.
- Never add a link or URL in this stream. Do not write a "link in bio" line."""

SEO_RULES_WITH_LINK = """SEO (search traction for strokesedge.com and the Substack picks article):
- Name the tournament in full and the course naturally,
  and use the weekly hashtag when it fits.
- Use natural search phrases a golf fan would type (e.g. "{tournament} picks",
  "best bets", "course fit") where the content allows it.
- Hashtag: use ONLY the exact weekly hashtag {hashtag}. Never shorten it or invent other hashtags.
- The strokesedge.com link is the call to action: give the reader a reason
  to click in a few words (free picks, full model breakdown, pick tracker).
  The free weekly picks live on the StrokesEdge Substack: mention
  "free picks on our Substack" only when there is room after the required link."""
