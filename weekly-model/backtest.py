#!/usr/bin/env python3
"""
backtest.py — validates the GENERAL scoring machinery (softmax temperature,
percentile-based L1 scaling) against past 2026 tournaments, letting the
weight-proposal step choose its own course-specific weights naturally for
each tournament (not held constant across events). Standalone diagnostic
script — does NOT touch production state.json/weights_proposal.md files
and does NOT send email.

LEAKAGE CONSTRAINT (a real data limitation, not a simplification chosen
for convenience):
Data Golf's preds/skill-ratings, preds/player-decompositions, and
preds/approach-skill endpoints are live-only snapshots with no "as of a
past date" parameter — there is no historical archive of any of them.
Only historical-raw-data/rounds carries real per-event dates. So for this
backtest:
  - sg_app_blend / sg_putt_blend / sg_arg_blend / sg_ott_blend / bob_pct
    ARE computed leak-free: a season-to-date baseline (Jan 1 of that year
    through the day before the target event started) blended 60/40 with
    a computed L30 window, both built from historical-raw-data/rounds
    filtered strictly before the event — same blend formula as
    production, just with the "as of" date moved back in time instead of
    "today."
  - Every player-decompositions-derived factor (cf_approach_comp,
    cf_short_comp, driving_accuracy_adjustment, driving_distance_adjustment,
    course_history_adjustment, course_experience_adjustment,
    major_adjustment) and every approach-skill-derived factor (the
    prox_* and rough_recovery_over150 keys) has NO historical source at
    all and is always None here. If Claude's natural weight proposal
    leans on them, run_l1()'s existing renormalization (real production
    code, not special-cased for this script) excludes them from that
    player's average rather than assuming a value. weight_coverage_pct
    on every result shows how much of the proposed weight was actually
    usable that week — report it, don't hide it.
"""
import statistics
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weekly_model_pipeline as wmp

BACKTEST_EVENTS = [
    {"event_id": 14, "event_name": "Masters Tournament", "course_name": "Augusta National Golf Club",
     "location": "Augusta, GA", "start_date": "2026-04-09"},
    {"event_id": 26, "event_name": "U.S. Open", "course_name": "Shinnecock Hills Golf Club",
     "location": "Southampton, NY", "start_date": "2026-06-18"},
    {"event_id": 11, "event_name": "THE PLAYERS Championship", "course_name": "TPC Sawgrass - THE PLAYERS Stadium Course",
     "location": "Ponte Vedra Beach, FL", "start_date": "2026-03-12"},
    {"event_id": 30, "event_name": "John Deere Classic", "course_name": "TPC Deere Run",
     "location": "Silvis, IL", "start_date": "2026-07-02"},
    {"event_id": 3, "event_name": "WM Phoenix Open", "course_name": "TPC Scottsdale (Stadium Course)",
     "location": "Scottsdale, AZ", "start_date": "2026-02-05"},
]


def fetch_event_field_and_results(event_id: int, year: int) -> dict:
    return wmp.dg_get("historical-raw-data/rounds", {"tour": "pga", "event_id": event_id, "year": year})


def parse_finish_rank(fin_text, worst_rank: int):
    if fin_text is None:
        return None
    t = str(fin_text).strip().upper()
    if t in ("CUT", "WD", "DQ", "MDF"):
        return worst_rank
    if t.startswith("T"):
        t = t[1:]
    try:
        return int(t)
    except ValueError:
        return None


def compute_windowed_stats(rounds_by_event: dict, window_start: date, window_end: date) -> dict:
    """Same aggregation as wmp.compute_l30_and_bob, generalized to an
    arbitrary window so it can compute either a season-to-date baseline
    or an L30 window as of any historical cutoff date."""
    accum = {}
    for event in rounds_by_event.values():
        if not isinstance(event, dict):
            continue
        completed_raw = event.get("event_completed")
        if not completed_raw:
            continue
        try:
            completed = date.fromisoformat(completed_raw[:10])
        except ValueError:
            continue
        if not (window_start <= completed <= window_end):
            continue
        for score in event.get("scores", []):
            dg_id = score.get("dg_id")
            if dg_id is None:
                continue
            bucket = accum.setdefault(dg_id, {"sg_app": [], "sg_arg": [], "sg_ott": [], "sg_putt": [],
                                                "birdies_plus": 0, "holes": 0, "rounds": 0})
            for rk, rv in score.items():
                if not rk.startswith("round_") or not isinstance(rv, dict):
                    continue
                bucket["rounds"] += 1
                for stat in ("sg_app", "sg_arg", "sg_ott", "sg_putt"):
                    if isinstance(rv.get(stat), (int, float)):
                        bucket[stat].append(rv[stat])
                bucket["birdies_plus"] += (rv.get("birdies") or 0) + (rv.get("eagles_or_better") or 0)
                bucket["holes"] += 18
    out = {}
    for dg_id, b in accum.items():
        out[dg_id] = {
            "sg_app": sum(b["sg_app"]) / len(b["sg_app"]) if b["sg_app"] else None,
            "sg_arg": sum(b["sg_arg"]) / len(b["sg_arg"]) if b["sg_arg"] else None,
            "sg_ott": sum(b["sg_ott"]) / len(b["sg_ott"]) if b["sg_ott"] else None,
            "sg_putt": sum(b["sg_putt"]) / len(b["sg_putt"]) if b["sg_putt"] else None,
            "bob_pct": (b["birdies_plus"] / b["holes"] * 100.0) if b["holes"] else None,
            "rounds": b["rounds"],
        }
    return out


def build_backtest_metrics(field_result: dict, season_stats: dict, l30_stats: dict) -> dict:
    metrics = {}
    for score in field_result.get("scores", []):
        dg_id = score.get("dg_id")
        if dg_id is None:
            continue
        season = season_stats.get(dg_id)
        l30 = l30_stats.get(dg_id)
        sample_ok = bool(season and season.get("rounds", 0) >= 5)

        def blended(stat_key, season=season, l30=l30):
            base = season.get(stat_key) if season else None
            if base is None:
                return None
            if l30 and l30.get(stat_key) is not None and l30.get("rounds", 0) >= wmp.L30_MIN_ROUNDS:
                return round(0.60 * base + 0.40 * l30[stat_key], 4)
            return base

        factors = {k: None for k in wmp.FACTOR_CATALOG}
        factors["sg_app_blend"] = blended("sg_app")
        factors["sg_putt_blend"] = blended("sg_putt")
        factors["sg_arg_blend"] = blended("sg_arg")
        factors["sg_ott_blend"] = blended("sg_ott")
        factors["bob_pct"] = season.get("bob_pct") if season else None

        metrics[dg_id] = {
            "player_name": score.get("player_name", f"dg_id {dg_id}"),
            "sample_ok": sample_ok,
            "l30_available": bool(l30),
            "factors": factors,
            "actual_fin_text": score.get("fin_text"),
        }
    return metrics


def spearman(pairs: list):
    """Rank-transform then Pearson — exactly what Spearman's rho is, no
    scipy dependency needed for a one-off diagnostic script."""
    if len(pairs) < 3:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    def ranks(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        r = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg_rank
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    n = len(pairs)
    mean_rx, mean_ry = sum(rx) / n, sum(ry) / n
    cov = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
    sx = sum((v - mean_rx) ** 2 for v in rx) ** 0.5
    sy = sum((v - mean_ry) ** 2 for v in ry) ** 0.5
    if sx == 0 or sy == 0:
        return None
    return cov / (sx * sy)


def run_backtest():
    year = 2026
    print("Pre-fetching full-season historical rounds (cached across all events)...")
    wmp.get_year_rounds_cached("pga", year)

    report = []
    for ev_spec in BACKTEST_EVENTS:
        event_id = ev_spec["event_id"]
        start = date.fromisoformat(ev_spec["start_date"])
        cutoff = start - timedelta(days=1)  # strictly before tournament week — no leakage
        l30_start = cutoff - timedelta(days=wmp.L30_WINDOW_DAYS)
        season_start = date(year, 1, 1)

        print(f"\n=== {ev_spec['event_name']} ({ev_spec['start_date']}) ===")
        field_result = fetch_event_field_and_results(event_id, year)
        rounds_by_event = wmp.get_year_rounds_cached("pga", year)

        season_stats = compute_windowed_stats(rounds_by_event, season_start, cutoff)
        l30_stats = compute_windowed_stats(rounds_by_event, l30_start, cutoff)

        course_facts = wmp.wikipedia_course_facts(ev_spec["course_name"])
        is_major = wmp.is_major_event(ev_spec["event_name"])
        event_for_prompt = {"event_name": ev_spec["event_name"], "course_name": ev_spec["course_name"],
                             "location": ev_spec["location"]}
        raw = None
        for attempt in range(3):
            try:
                raw = wmp.propose_weights(event_for_prompt, course_facts, is_major)
                break
            except Exception as e:
                print(f"  Claude API call failed (attempt {attempt + 1}/3): {e}")
                if attempt < 2:
                    time.sleep(5)
        if raw is None:
            print(f"  Giving up on {ev_spec['event_name']} after 3 attempts — skipping this event")
            report.append({"event": ev_spec["event_name"], "n_scored": 0, "rho_l1": None,
                            "rho_prob": None, "coverage_median": None, "top_prob": None})
            continue
        proposal = wmp.parse_claude_weight_response(raw)
        print("Proposed weights: " + ", ".join(f"{w['key']}={w['weight_pct']:g}%" for w in proposal["weights"]))

        metrics = build_backtest_metrics(field_result, season_stats, l30_stats)
        l1_results = wmp.run_l1(metrics, proposal["weights"])
        probs = wmp.softmax_probabilities({k: v["l1_score"] for k, v in l1_results.items()})

        worst_rank = len(metrics) + 5
        pairs_l1, pairs_prob, rows = [], [], []
        for dg_id, m in metrics.items():
            if not m["sample_ok"] or dg_id not in l1_results or l1_results[dg_id]["l1_score"] is None:
                continue
            actual = parse_finish_rank(m["actual_fin_text"], worst_rank)
            if actual is None:
                continue
            l1 = l1_results[dg_id]["l1_score"]
            prob = probs.get(dg_id, 0.0)
            pairs_l1.append((l1, -actual))
            pairs_prob.append((prob, -actual))
            rows.append((m["player_name"], l1, prob, l1_results[dg_id]["weight_coverage_pct"], m["actual_fin_text"]))

        rho_l1 = spearman(pairs_l1)
        rho_prob = spearman(pairs_prob)
        coverage = [r[3] for r in rows]
        top10 = sorted(rows, key=lambda r: r[1], reverse=True)[:10]

        rho_l1_str = f"{rho_l1:+.3f}" if rho_l1 is not None else "n/a"
        rho_prob_str = f"{rho_prob:+.3f}" if rho_prob is not None else "n/a"
        print(f"Players scored: {len(rows)} | Spearman(L1, actual finish): {rho_l1_str} | "
              f"Spearman(MDL PROB%, actual finish): {rho_prob_str}")
        if coverage:
            print(f"weight_coverage_pct — min {min(coverage):.0f}%, median {statistics.median(coverage):.0f}%, "
                  f"max {max(coverage):.0f}%")
        print("Top 10 by L1 score vs actual finish:")
        for name, l1, prob, cov, fin in top10:
            print(f"  {name:28s} L1={l1:5.1f}  MDL={prob:5.2f}%  coverage={cov:5.1f}%  actual={fin}")

        report.append({
            "event": ev_spec["event_name"], "n_scored": len(rows),
            "rho_l1": rho_l1, "rho_prob": rho_prob,
            "coverage_median": statistics.median(coverage) if coverage else None,
            "top_prob": max((r[2] for r in rows), default=None),
        })

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    for r in report:
        cov = f"{r['coverage_median']:.0f}%" if r['coverage_median'] is not None else "n/a"
        tp = f"{r['top_prob']:.2f}%" if r['top_prob'] is not None else "n/a"
        rl1 = f"{r['rho_l1']:+.3f}" if r['rho_l1'] is not None else "n/a"
        rp = f"{r['rho_prob']:+.3f}" if r['rho_prob'] is not None else "n/a"
        print(f"{r['event']:32s} n={r['n_scored']:3d}  rho(L1)={rl1}  rho(MDL%)={rp}  "
              f"coverage_med={cov}  top_prob={tp}")

    valid_rho = [r["rho_l1"] for r in report if r["rho_l1"] is not None]
    if valid_rho:
        print(f"\nMean rho(L1, actual finish) across {len(valid_rho)} events: {sum(valid_rho)/len(valid_rho):+.3f}")

    return report


if __name__ == "__main__":
    run_backtest()
