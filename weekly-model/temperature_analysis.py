#!/usr/bin/env python3
"""
temperature_analysis.py — follow-up to backtest.py. Reuses the EXACT
weight proposals Claude already returned during the completed backtest run
(hardcoded below, copied verbatim from that run's output) rather than
calling the Claude API again — this is a deterministic re-analysis of
already-computed L1 scores at different softmax temperatures, zero
additional API spend.

Rank correlation (Spearman) between L1 and actual finish is mathematically
invariant to the softmax temperature — softmax is a strictly monotonic
transform of L1, so it cannot change any pair's relative order. This
script exists to check the thing temperature CAN change: whether MDL PROB%
looks like a sane probability (top-favorite magnitude, spread across the
field) at different settings, so a recommendation can be made on evidence
rather than a guess.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weekly_model_pipeline as wmp
from backtest import BACKTEST_EVENTS, build_backtest_metrics, compute_windowed_stats, \
    fetch_event_field_and_results, parse_finish_rank, spearman

# Copied verbatim from the completed backtest.py run's printed output —
# NOT re-requested from Claude.
PROPOSED_WEIGHTS = {
    "Masters Tournament": [
        {"key": "sg_app_blend", "weight_pct": 19}, {"key": "cf_approach_comp", "weight_pct": 10},
        {"key": "sg_arg_blend", "weight_pct": 10}, {"key": "cf_short_comp", "weight_pct": 9},
        {"key": "sg_putt_blend", "weight_pct": 12}, {"key": "sg_ott_blend", "weight_pct": 10},
        {"key": "driving_distance_adjustment", "weight_pct": 8}, {"key": "driving_accuracy_adjustment", "weight_pct": 3},
        {"key": "course_history_adjustment", "weight_pct": 5}, {"key": "course_experience_adjustment", "weight_pct": 4},
        {"key": "major_adjustment", "weight_pct": 5}, {"key": "bob_pct", "weight_pct": 5},
    ],
    "U.S. Open": [
        {"key": "sg_app_blend", "weight_pct": 20}, {"key": "cf_approach_comp", "weight_pct": 12},
        {"key": "driving_accuracy_adjustment", "weight_pct": 12}, {"key": "sg_ott_blend", "weight_pct": 10},
        {"key": "sg_arg_blend", "weight_pct": 8}, {"key": "rough_recovery_over150", "weight_pct": 8},
        {"key": "sg_putt_blend", "weight_pct": 8}, {"key": "cf_short_comp", "weight_pct": 7},
        {"key": "major_adjustment", "weight_pct": 6}, {"key": "course_history_adjustment", "weight_pct": 4},
        {"key": "course_experience_adjustment", "weight_pct": 3}, {"key": "driving_distance_adjustment", "weight_pct": 2},
    ],
    "THE PLAYERS Championship": [
        {"key": "sg_app_blend", "weight_pct": 17}, {"key": "cf_approach_comp", "weight_pct": 11},
        {"key": "sg_arg_blend", "weight_pct": 11}, {"key": "cf_short_comp", "weight_pct": 9},
        {"key": "driving_accuracy_adjustment", "weight_pct": 9}, {"key": "sg_ott_blend", "weight_pct": 6},
        {"key": "sg_putt_blend", "weight_pct": 8}, {"key": "course_history_adjustment", "weight_pct": 6},
        {"key": "course_experience_adjustment", "weight_pct": 5}, {"key": "bob_pct", "weight_pct": 5},
        {"key": "prox_100_150_fw", "weight_pct": 4}, {"key": "prox_150_200_fw", "weight_pct": 3},
        {"key": "rough_recovery_over150", "weight_pct": 3}, {"key": "driving_distance_adjustment", "weight_pct": 3},
    ],
    "John Deere Classic": [
        {"key": "sg_app_blend", "weight_pct": 18}, {"key": "sg_putt_blend", "weight_pct": 15},
        {"key": "sg_arg_blend", "weight_pct": 12}, {"key": "cf_approach_comp", "weight_pct": 10},
        {"key": "cf_short_comp", "weight_pct": 9}, {"key": "bob_pct", "weight_pct": 10},
        {"key": "prox_100_150_fw", "weight_pct": 8}, {"key": "driving_accuracy_adjustment", "weight_pct": 6},
        {"key": "driving_distance_adjustment", "weight_pct": 4}, {"key": "course_history_adjustment", "weight_pct": 4},
        {"key": "course_experience_adjustment", "weight_pct": 4},
    ],
    "WM Phoenix Open": [
        {"key": "sg_app_blend", "weight_pct": 15}, {"key": "sg_putt_blend", "weight_pct": 14},
        {"key": "sg_arg_blend", "weight_pct": 9}, {"key": "sg_ott_blend", "weight_pct": 8},
        {"key": "cf_approach_comp", "weight_pct": 9}, {"key": "cf_short_comp", "weight_pct": 6},
        {"key": "driving_accuracy_adjustment", "weight_pct": 4}, {"key": "driving_distance_adjustment", "weight_pct": 6},
        {"key": "course_history_adjustment", "weight_pct": 4}, {"key": "course_experience_adjustment", "weight_pct": 3},
        {"key": "bob_pct", "weight_pct": 8}, {"key": "prox_100_150_fw", "weight_pct": 8},
        {"key": "prox_150_200_fw", "weight_pct": 4}, {"key": "rough_recovery_over150", "weight_pct": 2},
    ],
}
for _weights in PROPOSED_WEIGHTS.values():
    for _w in _weights:
        _w["rationale"] = "(reused from completed backtest run)"

CANDIDATE_TEMPERATURES = [8.0, 10.0, 12.0, 15.0, 20.0, 25.0]


def softmax_at_temperature(l1_scores: dict, temperature: float) -> dict:
    import math
    scored = {k: v for k, v in l1_scores.items() if v is not None}
    if not scored:
        return {}
    top = max(scored.values())
    exps = {k: math.exp((v - top) / temperature) for k, v in scored.items()}
    total = sum(exps.values())
    return {k: e / total * 100.0 for k, e in exps.items()}


def main():
    year = 2026
    print("Loading cached historical rounds (no new API calls for weights)...")
    wmp.get_year_rounds_cached("pga", year)

    all_results = {t: [] for t in CANDIDATE_TEMPERATURES}
    per_event_detail = []

    for ev_spec in BACKTEST_EVENTS:
        event_id = ev_spec["event_id"]
        start = date.fromisoformat(ev_spec["start_date"])
        cutoff = start - timedelta(days=1)
        l30_start = cutoff - timedelta(days=wmp.L30_WINDOW_DAYS)
        season_start = date(year, 1, 1)

        field_result = fetch_event_field_and_results(event_id, year)
        rounds_by_event = wmp.get_year_rounds_cached("pga", year)
        season_stats = compute_windowed_stats(rounds_by_event, season_start, cutoff)
        l30_stats = compute_windowed_stats(rounds_by_event, l30_start, cutoff)
        metrics = build_backtest_metrics(field_result, season_stats, l30_stats)

        weights = PROPOSED_WEIGHTS[ev_spec["event_name"]]
        l1_results = wmp.run_l1(metrics, weights)

        worst_rank = len(metrics) + 5
        actuals = {}
        for dg_id, m in metrics.items():
            if not m["sample_ok"] or dg_id not in l1_results or l1_results[dg_id]["l1_score"] is None:
                continue
            a = parse_finish_rank(m["actual_fin_text"], worst_rank)
            if a is not None:
                actuals[dg_id] = a

        l1_by_id = {k: v["l1_score"] for k, v in l1_results.items() if k in actuals}
        detail = {"event": ev_spec["event_name"], "n": len(l1_by_id), "by_temp": {}}

        for temp in CANDIDATE_TEMPERATURES:
            probs = softmax_at_temperature(l1_by_id, temp)
            pairs = [(probs[d], -actuals[d]) for d in l1_by_id]
            rho = spearman(pairs)
            top_prob = max(probs.values())
            sorted_probs = sorted(probs.values(), reverse=True)
            top5_cum = sum(sorted_probs[:5])
            rank10 = sorted_probs[9] if len(sorted_probs) > 9 else None
            ratio = (top_prob / rank10) if rank10 else None
            detail["by_temp"][temp] = {
                "rho": rho, "top_prob": top_prob, "top5_cum": top5_cum,
                "rank10_prob": rank10, "top_to_10th_ratio": ratio,
            }
            all_results[temp].append({"rho": rho, "top_prob": top_prob, "top5_cum": top5_cum})

        per_event_detail.append(detail)
        print(f"\n=== {ev_spec['event_name']} (n={detail['n']}) ===")
        print(f"{'T':>6} {'rho':>8} {'top_prob':>10} {'top5_cum':>10} {'rank10':>8} {'top:10th':>9}")
        for temp in CANDIDATE_TEMPERATURES:
            d = detail["by_temp"][temp]
            r10 = f"{d['rank10_prob']:.2f}%" if d["rank10_prob"] is not None else "n/a"
            ratio = f"{d['top_to_10th_ratio']:.1f}x" if d["top_to_10th_ratio"] else "n/a"
            print(f"{temp:6.1f} {d['rho']:+8.3f} {d['top_prob']:9.2f}% {d['top5_cum']:9.2f}% {r10:>8} {ratio:>9}")

    print("\n" + "=" * 78)
    print("AGGREGATE ACROSS ALL 5 EVENTS, BY TEMPERATURE")
    print("=" * 78)
    print(f"{'T':>6} {'mean rho':>10} {'mean top_prob':>15} {'mean top5_cum':>15}")
    for temp in CANDIDATE_TEMPERATURES:
        rows = all_results[temp]
        mean_rho = sum(r["rho"] for r in rows) / len(rows)
        mean_top = sum(r["top_prob"] for r in rows) / len(rows)
        mean_top5 = sum(r["top5_cum"] for r in rows) / len(rows)
        print(f"{temp:6.1f} {mean_rho:+10.3f} {mean_top:14.2f}% {mean_top5:14.2f}%")

    Path("temperature_analysis_output.json").write_text(json.dumps(per_event_detail, indent=2), encoding="utf-8")
    print("\nFull detail written to temperature_analysis_output.json")


if __name__ == "__main__":
    main()
