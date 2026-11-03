"""
Branded PNG chart generation for tweet/email attachments. Rebuilt on PIL
directly (2026-08-06) after the matplotlib version came out flat/generic —
matplotlib is a data-plotting library, not a design tool, so this draws
every element (color blocks, rounded bars, numbered rank boxes, tile
grids) by hand with ImageDraw for real typographic hierarchy, the same
category of design as the site's own picks-adjacent graphics: bold
condensed headline type, color blocks, no photo-composited imagery.

No reference file for "the same approach as wyndham_picks_banner.png"
existed anywhere in this repo or filesystem when this was built (checked
directly, not assumed) — this style is built from the written spec only
(dark bg, green accent, bold condensed headline, monospace data, color-
block hierarchy), not copied from a file nobody could locate.

Fonts, verified to actually render on this system before building around
them (same isolated-render-and-inspect discipline that caught the earlier
Calibri fontsize-9 blank-glyph bug):
    Headlines: Tw Cen MT Condensed Extra Bold (C:\\Windows\\Fonts\\TCCEB.TTF)
        — stands in for the site's actual Bebas Neue (not installed here).
        "DejaVuSansCondensed-Bold" was requested at one point but does not
        exist anywhere on this system or as a real DejaVu family release;
        flagged rather than silently substituted.
    Data/labels: Consolas / Consolas Bold — real monospace already
        installed, stands in for the site's DM Mono (also not installed
        locally as a font file, same situation as Calibri vs. DM Mono
        noted in this file's git history).

Scope: course_facts/methodology/course_fit only this phase — see
CHART_CATEGORIES. weather/recap/picks-adjacent content is intentionally
NOT wired into should_chart()'s automatic trigger path — it needs
tracker-CSV-sourced data to stay content-accurate and was scoped as a
later phase. generate_rankings_chart() exists and is demoed with real
tracker data below, but nothing in stream1_auto/stream2_manual's current
category rotation calls it automatically yet.

Every public generate_* function returns a Path on success or None on any
failure — failures are caught inside this module (never raised) so a
chart problem can never be the thing that blocks a post/email.
"""

import os
import time
import textwrap

from PIL import Image, ImageDraw, ImageFont

from tournament_config import TOURNAMENT, MODEL_WEIGHTS, COURSE_STATS

# Scope gate for the automatic per-tweet trigger path (should_chart /
# generate_chart_for_slot) — course_facts/methodology/course_fit only.
CHART_CATEGORIES = {"course_facts", "methodology", "course_fit"}

# ─────────────────────────────────────────────────────────────────────────
# Brand colors — same values used throughout this pipeline and in
# weekly-model/weekly_model_pipeline.py's real customer-copy workbooks.
# ─────────────────────────────────────────────────────────────────────────
COLOR_BG_DARK = "#080b07"
COLOR_GREEN = "#6ab83a"
COLOR_SECTION_FILL = "#1c3a14"
COLOR_MUTED_GREEN = "#a8c4a0"
COLOR_WHITE = "#ffffff"

CANVAS_W, CANVAS_H = 1200, 675
MARGIN = 60

HEADLINE_FONT_PATH = r"C:\Windows\Fonts\TCCEB.TTF"       # Tw Cen MT Condensed Extra Bold
DATA_BOLD_FONT_PATH = r"C:\Windows\Fonts\consolab.ttf"    # Consolas Bold
DATA_FONT_PATH = r"C:\Windows\Fonts\consola.ttf"          # Consolas

_font_cache = {}


def _font(path, size):
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]


def _headline(size):
    return _font(HEADLINE_FONT_PATH, size)


def _data_bold(size):
    return _font(DATA_BOLD_FONT_PATH, size)


def _data(size):
    return _font(DATA_FONT_PATH, size)


def _text_w(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _text_h(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _draw_right_aligned(draw, right_x, y, text, font, fill):
    w = _text_w(draw, text, font)
    draw.text((right_x - w, y), text, font=font, fill=fill)
    return w


def _wrap_to_width(draw, text, font, max_width):
    """Greedy word wrap using real glyph measurement, not a fixed char
    count — condensed fonts pack characters tighter than a naive
    textwrap.wrap(width=N) guess would assume."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if _text_w(draw, trial, font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _truncate_to_width(draw, text, font, max_width):
    """Truncate with an ellipsis rather than let long text (e.g. a
    multi-name parlay entry) run into whatever's laid out to its right —
    real glyph measurement, not a guessed character count."""
    if _text_w(draw, text, font) <= max_width:
        return text
    ellipsis = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _text_w(draw, text[:mid] + ellipsis, font) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + ellipsis


def _new_canvas():
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), COLOR_BG_DARK)
    return img, ImageDraw.Draw(img)


def _wordmark(draw):
    """Small brand tag, bottom-right, on every chart — same corner on all
    three types so charts read as StrokesEdge even without caption text."""
    text = "STROKESEDGE"
    font = _headline(22)
    w = _text_w(draw, text, font)
    x = CANVAS_W - MARGIN - w
    y = CANVAS_H - 44
    draw.rectangle([x - 16, y + 4, x - 10, y + 20], fill=COLOR_GREEN)  # small accent block
    draw.text((x, y - 2), text, font=font, fill=COLOR_MUTED_GREEN)


def _header(draw, headline_text, subtitle_text=None):
    draw.text((MARGIN, 42), headline_text.upper(), font=_headline(54), fill=COLOR_GREEN)
    if subtitle_text:
        draw.text((MARGIN, 108), subtitle_text.upper(), font=_data_bold(16), fill=COLOR_MUTED_GREEN)
    draw.line([(MARGIN, 150), (CANVAS_W - MARGIN, 150)], fill=COLOR_SECTION_FILL, width=2)


# ─────────────────────────────────────────────────────────────────────────
# 1. Rankings list — numbered rows, rank in a bold color block, name, stat.
# Not wired into should_chart()'s automatic path (see module docstring) —
# built and demoed now with real tracker data, ready for when picks-
# adjacent content is actually in scope.
# ─────────────────────────────────────────────────────────────────────────
def generate_rankings_chart(title, subtitle, rows, out_path):
    """rows: list of (rank:int, name:str, stat_label:str, stat_value:str),
    already sorted and capped by the caller (max ~6 fits the canvas
    cleanly). Every value must already trace to a real source — this
    function only lays them out, it doesn't compute or invent anything."""
    try:
        img, draw = _new_canvas()
        _header(draw, title, subtitle)

        row_h = 78
        top = 172
        for i, (rank, name, stat_label, stat_value) in enumerate(rows[:6]):
            y = top + i * row_h
            if i % 2 == 1:
                draw.rounded_rectangle([MARGIN - 20, y, CANVAS_W - MARGIN + 20, y + row_h - 8],
                                        radius=8, fill=COLOR_SECTION_FILL)

            box_size = 58
            draw.rounded_rectangle([MARGIN, y + 6, MARGIN + box_size, y + 6 + box_size],
                                    radius=10, fill=COLOR_GREEN)
            rank_text = str(rank)
            rf = _headline(30)
            rw = _text_w(draw, rank_text, rf)
            draw.text((MARGIN + (box_size - rw) / 2, y + 10), rank_text, font=rf, fill=COLOR_BG_DARK)

            right_x = CANVAS_W - MARGIN
            stat_col_w = 260  # reserved so a long name can never run into the stat column
            name_x = MARGIN + box_size + 24
            name_font = _headline(30)
            name_max_w = (right_x - stat_col_w) - name_x
            name_text = _truncate_to_width(draw, name, name_font, name_max_w)
            draw.text((name_x, y + 16), name_text, font=name_font, fill=COLOR_WHITE)

            _draw_right_aligned(draw, right_x, y + 8, stat_label.upper(), _data(14), COLOR_MUTED_GREEN)
            _draw_right_aligned(draw, right_x, y + 26, stat_value, _data_bold(26), COLOR_GREEN)

        _wordmark(draw)
        img.save(out_path)
        return out_path
    except Exception as e:
        print(f"[chart_gen] rankings chart failed: {e!r}")
        return None


# ─────────────────────────────────────────────────────────────────────────
# 2. Methodology — horizontal bars, bold labels, prominent % callouts.
# ─────────────────────────────────────────────────────────────────────────
def generate_methodology_chart(model_weights, tournament_name, out_path):
    try:
        img, draw = _new_canvas()
        _header(draw, "MODEL WEIGHTS", f"{tournament_name} — TOP WEIGHTED FACTORS")

        top = list(model_weights[:5])
        max_val = max(v for _, v in top)
        track_x0 = MARGIN
        track_w = CANVAS_W - 2 * MARGIN - 90  # leave room on the right for the % callout
        row_h = 88
        y = 190

        for label, value in top:
            draw.text((track_x0, y), label.upper(), font=_data_bold(22), fill=COLOR_WHITE)

            bar_y = y + 34
            bar_h = 28
            draw.rounded_rectangle([track_x0, bar_y, track_x0 + track_w, bar_y + bar_h],
                                    radius=6, fill=COLOR_SECTION_FILL)
            bar_w = max(int(track_w * value / max_val), bar_h)  # never shorter than its own rounded end
            draw.rounded_rectangle([track_x0, bar_y, track_x0 + bar_w, bar_y + bar_h],
                                    radius=6, fill=COLOR_GREEN)

            pct_text = f"{value}%"
            draw.text((track_x0 + track_w + 14, bar_y + 1), pct_text, font=_data_bold(26), fill=COLOR_WHITE)

            y += row_h

        _wordmark(draw)
        img.save(out_path)
        return out_path
    except Exception as e:
        print(f"[chart_gen] methodology chart failed: {e!r}")
        return None


# ─────────────────────────────────────────────────────────────────────────
# 3. Course stat card — tile grid, big bold numbers, color-block hierarchy.
# ─────────────────────────────────────────────────────────────────────────
def _stat_tile(draw, x, y, w, h, label, value, value_font, value_lines=1):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=COLOR_SECTION_FILL)
    draw.text((x + 20, y + 16), label.upper(), font=_data_bold(15), fill=COLOR_MUTED_GREEN)
    if value_lines == 1:
        draw.text((x + 20, y + 42), value, font=value_font, fill=COLOR_WHITE)
    else:
        ty = y + 42
        for line in value:
            draw.text((x + 20, ty), line, font=value_font, fill=COLOR_WHITE)
            ty += _text_h(draw, "Ag", value_font) + 10


def generate_course_stat_card(course_stats, tournament_name, out_path):
    try:
        img, draw = _new_canvas()
        _header(draw, tournament_name, course_stats.get("location"))

        # Row 1 — three compact big-number tiles.
        row1_y, row1_h = 172, 140
        gap = 20
        tile_w = (CANVAS_W - 2 * MARGIN - 2 * gap) // 3
        big_num_font = _headline(46)

        compact_stats = []
        if "par" in course_stats:
            compact_stats.append(("PAR", str(course_stats["par"])))
        if "yardage" in course_stats:
            compact_stats.append(("YARDAGE", f"{course_stats['yardage']:,}"))
        if "fairway_acres" in course_stats:
            compact_stats.append(("FAIRWAY", f"{course_stats['fairway_acres']} acres"))

        for i, (label, value) in enumerate(compact_stats[:3]):
            x = MARGIN + i * (tile_w + gap)
            _stat_tile(draw, x, row1_y, tile_w, row1_h, label, value, big_num_font)

        # Row 2 — two wider tiles for longer descriptive facts, word-wrapped.
        row2_y, row2_h = row1_y + row1_h + gap, 150
        wide_tile_w = (CANVAS_W - 2 * MARGIN - gap) // 2
        wrap_font = _data_bold(19)

        long_stats = []
        if "notable_hole" in course_stats:
            long_stats.append(("KEY HOLE", course_stats["notable_hole"]))
        if "designer" in course_stats:
            long_stats.append(("DESIGNER", course_stats["designer"]))

        for i, (label, value) in enumerate(long_stats[:2]):
            x = MARGIN + i * (wide_tile_w + gap)
            lines = _wrap_to_width(draw, value, wrap_font, wide_tile_w - 40)
            _stat_tile(draw, x, row2_y, wide_tile_w, row2_h, label, lines, wrap_font, value_lines=len(lines))

        _wordmark(draw)
        img.save(out_path)
        return out_path
    except Exception as e:
        print(f"[chart_gen] course stat card failed: {e!r}")
        return None


def should_chart(category, text):
    """Judgment gate — only chart when the tweet is actually dense enough
    in chartable data for an image to add real value over text alone, not
    every tweet in an eligible category. Returns 'methodology',
    'course_stat', or None."""
    if category not in CHART_CATEGORIES:
        return None
    lowered = text.lower()

    if category == "methodology":
        if any(label.lower() in lowered for label, _ in MODEL_WEIGHTS):
            return "methodology"
        return None

    # course_facts / course_fit
    hits = 0
    par = COURSE_STATS.get("par")
    if par is not None and f"par {par}" in lowered:
        hits += 1
    yardage = COURSE_STATS.get("yardage")
    if yardage is not None and str(yardage) in text.replace(",", ""):
        hits += 1
    if "507" in text:  # the notable hole's yardage — distinctive enough to count alone
        hits += 1
    acres = COURSE_STATS.get("fairway_acres")
    if acres is not None and f"{acres} acres" in lowered:
        hits += 1
    return "course_stat" if hits >= 2 else None


def _alt_text_for(kind):
    if kind == "methodology":
        weights = ", ".join(f"{label} {value}%" for label, value in MODEL_WEIGHTS[:5])
        return f"Bar chart: StrokesEdge model weights for {TOURNAMENT['name']} — {weights}."
    facts = []
    if "par" in COURSE_STATS:
        facts.append(f"par {COURSE_STATS['par']}")
    if "yardage" in COURSE_STATS:
        facts.append(f"{COURSE_STATS['yardage']:,} yards")
    if "notable_hole" in COURSE_STATS:
        facts.append(COURSE_STATS["notable_hole"])
    return f"Stat card: {TOURNAMENT['name']} course facts — {', '.join(facts)}."


def generate_chart_for_slot(category, text, out_dir):
    """Top-level entry point both streams call — unchanged interface from
    the matplotlib version, only what happens inside changed. Returns
    (path, alt_text) on success, (None, None) if this slot isn't
    chart-worthy or generation failed for any reason. Callers must always
    handle (None, None) by falling back to text-only."""
    kind = should_chart(category, text)
    if kind is None:
        return None, None

    try:
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"chart_{category}_{int(time.time() * 1000)}.png")
    except Exception as e:
        print(f"[chart_gen] could not prepare output dir {out_dir!r}: {e!r}")
        return None, None

    if kind == "methodology":
        path = generate_methodology_chart(MODEL_WEIGHTS, TOURNAMENT["name"], out_path)
    else:
        path = generate_course_stat_card(COURSE_STATS, TOURNAMENT["name"], out_path)

    if path is None:
        return None, None
    return path, _alt_text_for(kind)


def cleanup_chart(path):
    """Best-effort delete — a leftover PNG must never crash a caller that's
    already done posting/emailing."""
    if not path:
        return
    try:
        os.remove(path)
    except Exception as e:
        print(f"[chart_gen] could not clean up {path!r}: {e!r}")


def _demo_rankings_rows_from_tracker():
    """Real open-bet rows for the current tournament, sorted by implied
    probability from the real American odds — a standard, non-invented
    transformation used only for ordering. Every displayed field (name,
    bet type, odds) is copied straight from the tracker row. Demo/CLI use
    only — not part of the automatic should_chart() trigger path."""
    from tracker import fetch_tracker_rows

    rows = fetch_tracker_rows()
    open_rows = [
        r for r in rows
        if TOURNAMENT["name"].lower() in (r.get("tournament") or "").lower()
        and (r.get("result") or "").strip().lower() == "open"
    ]

    def implied_prob(odds_str):
        o = int(odds_str)
        return 100 / (o + 100) if o > 0 else -o / (-o + 100)

    open_rows.sort(key=lambda r: implied_prob(r["odds"]), reverse=True)

    chart_rows = []
    for i, r in enumerate(open_rows[:6], 1):
        odds = int(r["odds"])
        odds_str = f"+{odds}" if odds > 0 else str(odds)
        chart_rows.append((i, r["player"], r["type"], odds_str))
    return chart_rows


if __name__ == "__main__":
    import tempfile

    tmp_dir = tempfile.mkdtemp()
    print(f"Writing sample charts to {tmp_dir}")
    p1 = generate_methodology_chart(MODEL_WEIGHTS, TOURNAMENT["name"],
                                     os.path.join(tmp_dir, "sample_methodology.png"))
    p2 = generate_course_stat_card(COURSE_STATS, TOURNAMENT["name"],
                                    os.path.join(tmp_dir, "sample_course_stat.png"))
    print("methodology chart:", p1)
    print("course stat card:", p2)

    try:
        rows = _demo_rankings_rows_from_tracker()
        if rows:
            p3 = generate_rankings_chart(
                TOURNAMENT["name"], "OPEN TRACKER BETS — SORTED BY IMPLIED PROBABILITY",
                rows, os.path.join(tmp_dir, "sample_rankings.png"),
            )
            print("rankings chart:", p3)
        else:
            print("rankings chart: skipped — no open tracker rows for the current tournament")
    except Exception as e:
        print(f"rankings chart: skipped — {e!r}")
