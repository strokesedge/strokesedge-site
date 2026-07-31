"""Crude HTML-to-text and local site-file loading, shared by both streams'
content-context builders (course facts, methodology, course-fit content
all pull from the same site pages)."""

import os
import re


def strip_html(raw_html):
    """Crude tag strip — good enough for feeding body text to the model as context."""
    text = re.sub(r"<script.*?</script>", "", raw_html, flags=re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_local_file(filename, site_repo):
    if not filename:
        return None
    path = os.path.join(site_repo, filename)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return strip_html(f.read())
