"""
Stream 1 — X API v2 media upload (initialize/append/finalize) plus
optional alt-text metadata, using OAuth 1.0a with the same X_* credentials
post_tweets.py already uses for create_tweet.

Hand-rolled via requests + requests_oauthlib rather than tweepy's built-in
API.media_upload(): confirmed by reading the installed tweepy 4.17.0
source (tweepy/api.py) that its media_upload() only ever targets the
legacy v1.1 media/upload endpoint — deprecated for self-serve developers
2025-03-31. tweepy.Client (v2) has no media_upload method at all. The v2
media endpoints support OAuth 1.0a UserToken auth directly (confirmed via
developer.x.com docs), so the existing 4-credential setup works unchanged;
this module just signs requests to the new URLs tweepy doesn't know about.
"""

import os
import time

import requests
from requests_oauthlib import OAuth1

MEDIA_BASE = "https://api.x.com/2/media/upload"
METADATA_URL = "https://api.x.com/2/media/metadata"


def _auth():
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
    return OAuth1(
        os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def upload_image(path, alt_text=None, timeout=30):
    """Uploads a local PNG via the v2 media upload flow and returns the
    resulting media_id (str) for tweepy.Client.create_tweet(media_ids=[...]).
    Raises on any failure — callers must catch and fall back to a
    text-only post, same contract as any other exception from this
    pipeline's X API calls.

    Only handles single-segment image uploads (our chart PNGs are a few
    hundred KB, well under any chunking threshold) — no multi-segment
    append loop, since this module never uploads video/gif."""
    auth = _auth()
    with open(path, "rb") as f:
        data = f.read()

    init_resp = requests.post(
        f"{MEDIA_BASE}/initialize", auth=auth, timeout=timeout,
        json={"media_type": "image/png", "total_bytes": len(data), "media_category": "tweet_image"},
    )
    init_resp.raise_for_status()
    media_id = init_resp.json()["data"]["id"]

    append_resp = requests.post(
        f"{MEDIA_BASE}/{media_id}/append", auth=auth, timeout=timeout,
        data={"segment_index": "0"},
        files={"media": ("chart.png", data, "image/png")},
    )
    append_resp.raise_for_status()

    finalize_resp = requests.post(f"{MEDIA_BASE}/{media_id}/finalize", auth=auth, timeout=timeout)
    finalize_resp.raise_for_status()
    processing_info = finalize_resp.json().get("data", {}).get("processing_info") or {}
    if processing_info.get("state") == "failed":
        raise RuntimeError(f"Media processing failed for media_id={media_id}: {processing_info}")
    # Images finalize synchronously in practice (state "succeeded" or no
    # processing_info at all) — unlike video/gif, which need polling a
    # status-check endpoint. Not implemented here since this module only
    # ever uploads static PNG charts; if that ever changes, this is the
    # place to add polling rather than assuming synchronous completion.

    if alt_text:
        meta_resp = requests.post(
            METADATA_URL, auth=auth, timeout=timeout,
            json={"id": media_id, "metadata": {"alt_text": {"text": alt_text[:1000]}}},
        )
        # Alt text is accessibility polish, not required for the upload to
        # count as a success — don't let a metadata hiccup discard an
        # otherwise-good image upload. Log and continue.
        if not meta_resp.ok:
            print(f"[x_media] alt text metadata call failed ({meta_resp.status_code}): {meta_resp.text[:200]}")

    return media_id
