"""
Derives every leaderboard/chart the site shows, from the raw fetched +
cached data. Every function here is pure (data in, data out, no API
calls) -- cheap to always recompute fresh on every run.

Formulas ported from the old dashboard's Queries.sql / confirmed against
real screenshots of the old Looker Studio report, EXCEPT where flagged
"best-guess" -- those two (Consistency, Average Position) had no old
screenshot with real numbers to confirm the exact formula against.
"""
from statistics import mean, pstdev

CHIP_LABELS = {
    "wildcard": "Wildcard",
    "freehit": "Free Hit",
    "bboost": "Bench Boost",
    "3xc": "Triple Captain",
}


def _points_by_gw(gameweeks, manager_id):
    return {row["gw"]: row for row in gameweeks[manager_id]}


def _global_average(bootstrap_events, gw):
    for event in bootstrap_events:
        if event["id"] == gw:
            return event.get("average_entry_score")
    return None


def _name(managers, manager_id):
    return managers[manager_id]["name"]


def compute_form(gameweeks, managers, finished_gws, window=5):
    """In Form/In Freefall, Sound Spenders/Spend Thrifts, Tactical
    Masters/Rotation Losers -- top-3/bottom-3 over the last `window`
    finished gameweeks."""
    recent_gws = finished_gws[-window:]

    def totals(field):
        result = {}
        for manager_id, rows in gameweeks.items():
            if ":chips" in manager_id:
                continue
            result[manager_id] = sum(
                row[field] for row in rows if row["gw"] in recent_gws
            )
        return result

    def top_bottom(totals_by_manager, ascending_is_better):
        ranked = sorted(
            totals_by_manager.items(), key=lambda kv: kv[1], reverse=not ascending_is_better
        )
        best = ranked[:3] if not ascending_is_better else ranked[:3]
        worst = ranked[-3:][::-1]
        fmt = lambda pairs: [
            {"manager_id": mid, "name": _name(managers, mid), "value": val}
            for mid, val in pairs
        ]
        return fmt(best), fmt(worst)

    points_totals = totals("points")
    cost_totals = totals("transfer_cost")
    bench_totals = totals("points_on_bench")

    in_form, in_freefall = top_bottom(points_totals, ascending_is_better=False)
    sound_spenders, spend_thrifts = top_bottom(cost_totals, ascending_is_better=True)
    tactical_masters, rotation_losers = top_bottom(bench_totals, ascending_is_better=True)

    return {
        "window_gws": recent_gws,
        "in_form": in_form,
        "in_freefall": in_freefall,
        "sound_spenders": sound_spenders,
        "spend_thrifts": spend_thrifts,
        "tactical_masters": tactical_masters,
        "rotation_losers": rotation_losers,
    }


def compute_bench_leaderboard(gameweeks, managers):
    """Points on Bench: total bench points per manager, this season."""
    totals = {
        mid: sum(row["points_on_bench"] for row in rows)
        for mid, rows in gameweeks.items()
        if ":chips" not in mid
    }
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return [
        {"manager_id": mid, "name": _name(managers, mid), "points_on_bench": pob}
        for mid, pob in ranked
    ]


def compute_adjusted_table(gameweeks, managers):
    """Adjusted Table + "Jammy Bastards": standings re-ranked by
    Total Pts + Total Bench Points, and the delta between real rank and
    this adjusted rank (positive = ranked better than bench-adjusted
    rank deserves = jammy)."""
    rows = []
    for mid, gws in gameweeks.items():
        if ":chips" in mid:
            continue
        total_pts = max((r["total_points"] for r in gws), default=0)
        pob = sum(r["points_on_bench"] for r in gws)
        rows.append(
            {
                "manager_id": mid,
                "name": _name(managers, mid),
                "points_on_bench": pob,
                "total_points": total_pts,
                "total_plus_bench": total_pts + pob,
            }
        )

    real_rank = {
        r["manager_id"]: i + 1
        for i, r in enumerate(sorted(rows, key=lambda r: r["total_points"], reverse=True))
    }
    adjusted_rank = {
        r["manager_id"]: i + 1
        for i, r in enumerate(sorted(rows, key=lambda r: r["total_plus_bench"], reverse=True))
    }

    for r in rows:
        r["real_rank"] = real_rank[r["manager_id"]]
        r["adjusted_rank"] = adjusted_rank[r["manager_id"]]
        # Positive => real rank number is worse than adjusted => jammy (benefited from luck).
        r["jammy_delta"] = adjusted_rank[r["manager_id"]] - real_rank[r["manager_id"]]

    rows.sort(key=lambda r: r["total_plus_bench"], reverse=True)
    return rows


def compute_points_on_bench_by_week(gameweeks, managers):
    return {
        mid: [{"gw": row["gw"], "points_on_bench": row["points_on_bench"]} for row in rows]
        for mid, rows in gameweeks.items()
        if ":chips" not in mid
    }


def compute_consistency(gameweeks, managers):
    """BEST-GUESS FORMULA (no old screenshot confirmed this with real
    numbers): population stdev of gw points across the season. Lower =
    more consistent. Flag to the user to confirm/adjust once they see
    real output."""
    result = []
    for mid, rows in gameweeks.items():
        if ":chips" in mid or len(rows) < 2:
            continue
        points = [r["points"] for r in rows]
        result.append(
            {
                "manager_id": mid,
                "name": _name(managers, mid),
                "consistency_stdev": round(pstdev(points), 2),
                "mean_points": round(mean(points), 2),
            }
        )
    result.sort(key=lambda r: r["consistency_stdev"])
    return result


def compute_league_positions(gameweeks):
    """{manager_id: [{gw, position}]} -- this league's own rank each
    gameweek, computed by ranking all managers' cumulative total_points
    at each gameweek. Not provided directly by the FPL API; needed for
    Average Position and Weeks at the Top / Podiums (this season)."""
    manager_ids = [mid for mid in gameweeks if ":chips" not in mid]
    all_gws = sorted({row["gw"] for mid in manager_ids for row in gameweeks[mid]})

    positions = {mid: [] for mid in manager_ids}
    for gw in all_gws:
        totals = [
            (mid, _points_by_gw(gameweeks, mid)[gw]["total_points"])
            for mid in manager_ids
            if gw in _points_by_gw(gameweeks, mid)
        ]
        totals.sort(key=lambda kv: kv[1], reverse=True)
        for i, (mid, _) in enumerate(totals):
            positions[mid].append({"gw": gw, "position": i + 1})
    return positions


def compute_average_position(league_positions, managers):
    """BEST-GUESS FORMULA: mean league position across the season."""
    result = []
    for mid, rows in league_positions.items():
        if not rows:
            continue
        avg = mean(r["position"] for r in rows)
        result.append({"manager_id": mid, "name": _name(managers, mid), "average_position": round(avg, 2)})
    result.sort(key=lambda r: r["average_position"])
    return result


def compute_weeks_at_top_and_podium(league_positions, managers):
    result = []
    for mid, rows in league_positions.items():
        weeks_top = sum(1 for r in rows if r["position"] == 1)
        weeks_podium = sum(1 for r in rows if r["position"] <= 3)
        result.append(
            {
                "manager_id": mid,
                "name": _name(managers, mid),
                "weeks_at_top": weeks_top,
                "weeks_on_podium": weeks_podium,
            }
        )
    return result


def compute_overall_rank_trend(gameweeks, managers):
    return {
        mid: [{"gw": row["gw"], "overall_rank": row["overall_rank"]} for row in rows]
        for mid, rows in gameweeks.items()
        if ":chips" not in mid
    }


def compute_league_progression(gameweeks, managers):
    return {
        mid: [{"gw": row["gw"], "total_points": row["total_points"]} for row in rows]
        for mid, rows in gameweeks.items()
        if ":chips" not in mid
    }


def compute_vs_average(gameweeks, managers, bootstrap_events):
    """Are You Average?: per-manager (points - global average) trended
    by gameweek, plus best/worst single-week margins and week-counts."""
    series = {}
    summary = []
    for mid, rows in gameweeks.items():
        if ":chips" in mid:
            continue
        manager_series = []
        for row in rows:
            avg = _global_average(bootstrap_events, row["gw"])
            if avg is None:
                continue
            manager_series.append({"gw": row["gw"], "vs_average": row["points"] - avg})
        series[mid] = manager_series

        beat = [s for s in manager_series if s["vs_average"] > 0]
        lost = [s for s in manager_series if s["vs_average"] < 0]
        summary.append(
            {
                "manager_id": mid,
                "name": _name(managers, mid),
                "weeks_beat_average": len(beat),
                "best_vs_average": max((s["vs_average"] for s in beat), default=0),
                "weeks_lost_to_average": len(lost),
                "worst_vs_average": min((s["vs_average"] for s in lost), default=0),
            }
        )

    return {"series": series, "summary": summary}


def compute_league_vs_global_average(gameweeks, bootstrap_events, finished_gws):
    """Sportz Chat v Average + Best Weeks: this league's own average
    score each gameweek vs. the whole-FPL average that gameweek."""
    manager_ids = [mid for mid in gameweeks if ":chips" not in mid]
    series = []
    for gw in finished_gws:
        gw_points = [
            _points_by_gw(gameweeks, mid)[gw]["points"]
            for mid in manager_ids
            if gw in _points_by_gw(gameweeks, mid)
        ]
        if not gw_points:
            continue
        league_total = sum(gw_points)
        league_average = league_total / len(gw_points)
        global_average = _global_average(bootstrap_events, gw)
        if global_average is None:
            continue
        series.append(
            {
                "gw": gw,
                "league_total": league_total,
                "league_average": round(league_average, 1),
                "global_average": global_average,
                "vs_average": round(league_average - global_average, 1),
            }
        )

    best_weeks = sorted(series, key=lambda r: r["vs_average"], reverse=True)[:10]
    return {"series": series, "best_weeks": best_weeks}


def compute_best_worst_scores(gameweeks, managers, bootstrap_events):
    """Individual manager-gameweek score records, league-wide."""
    all_scores = []
    for mid, rows in gameweeks.items():
        if ":chips" in mid:
            continue
        for row in rows:
            avg = _global_average(bootstrap_events, row["gw"])
            if avg is None:
                continue
            all_scores.append(
                {
                    "manager_id": mid,
                    "name": _name(managers, mid),
                    "gw": row["gw"],
                    "points": row["points"],
                    "hits": -row["transfer_cost"] if row["transfer_cost"] else 0,
                    "vs_average": row["points"] - avg,
                }
            )
    best = sorted(all_scores, key=lambda r: r["points"], reverse=True)[:10]
    worst = sorted(all_scores, key=lambda r: r["points"])[:10]
    return {"best_10": best, "worst_10": worst}


def compute_chip_usage(gameweeks, managers, bootstrap_events):
    """Chip Score v Average Score That Week (stacked by chip type),
    Top 10 Chips, and a Triple Captain-specific points table."""
    plays = []
    for mid, rows in gameweeks.items():
        if not mid.endswith(":chips"):
            continue
        manager_id = mid.split(":")[0]
        for chip in rows:
            gw = chip["event"]
            gw_row = next((r for r in gameweeks[manager_id] if r["gw"] == gw), None)
            avg = _global_average(bootstrap_events, gw)
            if gw_row is None or avg is None:
                continue
            plays.append(
                {
                    "manager_id": manager_id,
                    "name": _name(managers, manager_id),
                    "gw": gw,
                    "chip": chip["name"],
                    "chip_label": CHIP_LABELS.get(chip["name"], chip["name"]),
                    "points": gw_row["points"],
                    "vs_average": gw_row["points"] - avg,
                }
            )

    # Wildcard is played twice a season -- label chronologically per manager.
    by_manager_wildcards = {}
    for play in sorted(plays, key=lambda p: p["gw"]):
        if play["chip"] != "wildcard":
            continue
        n = by_manager_wildcards.get(play["manager_id"], 0) + 1
        by_manager_wildcards[play["manager_id"]] = n
        play["chip_label"] = f"Wildcard{n}"

    stacked = {}
    for play in plays:
        stacked.setdefault(play["manager_id"], {"name": play["name"], "chips": {}})
        stacked[play["manager_id"]]["chips"][play["chip_label"]] = play["vs_average"]

    top_10_chips = sorted(plays, key=lambda p: p["points"], reverse=True)[:10]
    # Match on chip_label (normalized display name), not the raw "chip"
    # code -- source data isn't always the raw FPL code ("3xc"); some
    # historic exports already stored the human label ("Triple Captain").
    triple_captain_points = sorted(
        (p for p in plays if p["chip_label"] == CHIP_LABELS["3xc"]),
        key=lambda p: p["points"],
        reverse=True,
    )

    return {
        "stacked_by_manager": stacked,
        "top_10_chips": top_10_chips,
        "triple_captain_points": triple_captain_points,
    }


def compute_captaincy_summary(captains, gameweeks, managers):
    """Can You Captain?: total captain points, weeks the best possible
    captain was picked, and cumulative gain/loss vs optimal."""
    summary = []
    series = {}
    for mid, gws in captains.items():
        total = sum(g["captain_points"] for g in gws.values())
        picked_best = sum(g["picked_best_captain"] for g in gws.values())
        gain_loss = sum(g["captain_delta"] for g in gws.values())
        summary.append(
            {
                "manager_id": mid,
                "name": _name(managers, mid),
                "total_captain_points": total,
                "picked_best_captain_weeks": picked_best,
                "gain_loss_vs_optimal": gain_loss,
            }
        )
        series[mid] = [
            {"gw": int(gw), "captain_points": g["captain_points"]}
            for gw, g in sorted(gws.items(), key=lambda kv: int(kv[0]))
        ]

    summary.sort(key=lambda r: r["total_captain_points"], reverse=True)
    return {"summary": summary, "series": series}


def compute_transfers_summary(transfers, managers):
    """Total Transfers / Total Points from Transfers + Best/Worst
    individual transfer swaps by net points."""
    summary = []
    all_transfers = []
    for mid, entries in transfers.items():
        total_net_points = sum(e["net_points"] for e in entries if e["net_points"] is not None)
        summary.append(
            {
                "manager_id": mid,
                "name": _name(managers, mid),
                "transfer_count": len(entries),
                "total_net_points": total_net_points,
            }
        )
        for e in entries:
            if e["net_points"] is None:
                continue
            all_transfers.append({**e, "manager_id": mid, "name": _name(managers, mid)})

    best = sorted(all_transfers, key=lambda t: t["net_points"], reverse=True)[:10]
    worst = sorted(all_transfers, key=lambda t: t["net_points"])[:10]
    return {"summary": summary, "best_transfers": best, "worst_transfers": worst}


def compute_top10_all_time(historic):
    """Best 10 individual season performances across all managers'
    history, ranked by overall_percentage ascending (lower = better
    percentile finish)."""
    rows = []
    for name, seasons in historic.items():
        for s in seasons:
            if s["overall_percentage"] is None:
                continue
            rows.append({"name": name, **s})
    rows.sort(key=lambda r: r["overall_percentage"])
    return rows[:10]


def compute_wins_and_podiums_alltime(historic):
    result = []
    for name, seasons in historic.items():
        wins = sum(1 for s in seasons if s["league_rank"] == 1)
        podiums = sum(1 for s in seasons if s["league_rank"] is not None and s["league_rank"] <= 3)
        result.append({"name": name, "wins": wins, "podiums": podiums})
    result.sort(key=lambda r: (-r["wins"], -r["podiums"]))
    return result


def compute_all(fetched, historic):
    gameweeks = fetched["gameweeks"]
    managers = fetched["managers"]
    bootstrap_events = fetched["bootstrap"]["events"]
    finished_gws = sorted(
        e["id"] for e in bootstrap_events if e.get("finished")
    )

    league_positions = compute_league_positions(gameweeks)

    return {
        "form": compute_form(gameweeks, managers, finished_gws),
        "bench_leaderboard": compute_bench_leaderboard(gameweeks, managers),
        "adjusted_table": compute_adjusted_table(gameweeks, managers),
        "points_on_bench_by_week": compute_points_on_bench_by_week(gameweeks, managers),
        "consistency": compute_consistency(gameweeks, managers),
        "average_position": compute_average_position(league_positions, managers),
        "weeks_at_top_and_podium": compute_weeks_at_top_and_podium(league_positions, managers),
        "overall_rank_trend": compute_overall_rank_trend(gameweeks, managers),
        "league_progression": compute_league_progression(gameweeks, managers),
        "vs_average": compute_vs_average(gameweeks, managers, bootstrap_events),
        "league_vs_global_average": compute_league_vs_global_average(
            gameweeks, bootstrap_events, finished_gws
        ),
        "best_worst_scores": compute_best_worst_scores(gameweeks, managers, bootstrap_events),
        "chip_usage": compute_chip_usage(gameweeks, managers, bootstrap_events),
        "captaincy": compute_captaincy_summary(fetched["captains"], gameweeks, managers),
        "transfers_summary": compute_transfers_summary(fetched["transfers"], managers),
        "top10_all_time": compute_top10_all_time(historic),
        "wins_and_podiums_alltime": compute_wins_and_podiums_alltime(historic),
        "predicted_points": None,  # TODO: deferred feature, not built yet
    }
