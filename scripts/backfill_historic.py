#!/usr/bin/env python3
"""
One-off (but re-runnable) backfill script. NOT part of the recurring
update workflow.

Fills gaps in docs/data/historic.json using each current-season
manager's own FPL entry history (`past` season summaries). Turns out
this league's members' current manager_ids are their long-standing
personal FPL accounts (some go back to 2008/09), so `past` covers
almost everything -- including two seasons entirely missing from the
originally recovered spreadsheet: 2024/25 and 2025/26.

What the API's `past` array gives us per season: total_points, rank
(whole-FPL rank). What it does NOT give us, which we derive instead:

  - overall_percentage = rank / total_players_that_season. FPL's API
    has no historical total_players endpoint. For seasons we already
    have real percentage figures on file, total_players is derived
    from existing (rank, percentage) pairs -- these cross-validate
    almost exactly against Wikipedia's published season-by-season FPL
    participation table (e.g. 2021/22 and 2022/23 match to the exact
    integer). For 2024/25 and 2025/26 -- entirely new seasons, no
    existing percentage to derive from -- total_players comes from
    Wikipedia's FPL article (https://en.wikipedia.org/wiki/Fantasy_Premier_League,
    checked August 2026): 11.50m and 13.10m respectively. Less precise
    than the derived figures for older seasons, but the best publicly
    available number.

  - league_rank = this friend group's own relative rank, computed by
    sorting whoever has data for that season by total_points. This is
    an approximation: it assumes everyone with data for that season
    was part of the same head-to-head group, which we can't formally
    verify season by season (this league's own FPL league object has
    been recreated multiple times). Flagged here, not hidden.

Run manually whenever there's a new season to backfill:
    python3 scripts/backfill_historic.py
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fpl_api
from identity import canonical_name

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "docs" / "data"
HISTORIC_PATH = DATA_DIR / "historic.json"
MANAGERS_PATH = DATA_DIR / "managers.json"

# Total FPL participants for seasons where we have no on-file rank+percentage
# pair to derive it from. Source: Wikipedia's Fantasy Premier League article,
# "Winners" table, checked August 2026.
WIKIPEDIA_TOTAL_PLAYERS = {
    "2024/25": 11_500_000,
    "2025/26": 13_100_000,
}

# The group's shared history starts 2013/14 (the earliest season most
# members have data for). Some individuals' personal FPL accounts go
# back further (e.g. 2008/09), but that's solo pre-league history for
# one or two people, not a real head-to-head season for this group --
# a "league_rank" of #1 out of one person is meaningless. Only backfill
# from the group's actual shared window onward.
EARLIEST_SEASON = "2013/14"


def derive_total_players(historic):
    """{season: total_players} derived from existing (rank, percentage)
    pairs already on file, using the median across all managers who
    have both fields for that season."""
    by_season = {}
    for seasons in historic.values():
        for s in seasons:
            if s.get("overall_rank") and s.get("overall_percentage"):
                estimate = round(s["overall_rank"] / s["overall_percentage"])
                by_season.setdefault(s["year"], []).append(estimate)
    return {year: round(statistics.median(vals)) for year, vals in by_season.items()}


def main():
    with open(HISTORIC_PATH) as f:
        historic = json.load(f)
    with open(MANAGERS_PATH) as f:
        managers = json.load(f)

    total_players_by_season = derive_total_players(historic)
    total_players_by_season.update(WIKIPEDIA_TOTAL_PLAYERS)

    # 1. Fetch each manager's full past-season history, keep only
    #    seasons not already on file for that canonical name.
    new_rows_by_season = {}  # season -> [{name, points, overall_rank}]
    for manager_id, m in managers.items():
        name = canonical_name(m["name"])
        existing_seasons = {s["year"] for s in historic.get(name, [])}
        history = fpl_api.get_entry_history(manager_id)
        for p in history.get("past", []):
            year = p["season_name"]
            if year < EARLIEST_SEASON or year in existing_seasons:
                continue
            new_rows_by_season.setdefault(year, []).append(
                {"name": name, "points": p["total_points"], "overall_rank": p["rank"]}
            )

    if not new_rows_by_season:
        print("No new seasons to backfill -- historic.json is already complete.")
        return

    # 2. For each new season, compute this group's own league_rank by
    #    sorting whoever has data for that season by points, and
    #    overall_percentage from total_players (if known for that year).
    added = 0
    for year, rows in sorted(new_rows_by_season.items()):
        rows.sort(key=lambda r: r["points"], reverse=True)
        total_players = total_players_by_season.get(year)
        if total_players is None:
            print(f"WARNING: no total_players figure for {year} -- skipping "
                  f"percentage calc for this season, adding rows without it.")

        for league_rank, row in enumerate(rows, start=1):
            entry = {
                "year": year,
                "points": row["points"],
                "overall_rank": row["overall_rank"],
                "overall_percentage": (
                    round(row["overall_rank"] / total_players, 6)
                    if total_players
                    else None
                ),
                "league_rank": league_rank,
                "manager_id": None,  # not meaningfully knowable retroactively
            }
            historic.setdefault(row["name"], []).append(entry)
            added += 1
            print(f"  {year}: #{league_rank} {row['name']} -- {row['points']} pts")

    for name in historic:
        historic[name].sort(key=lambda s: s["year"])

    with open(HISTORIC_PATH, "w") as f:
        json.dump(historic, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"\nAdded {added} season rows across {len(new_rows_by_season)} seasons.")
    print(f"Wrote {HISTORIC_PATH}")


if __name__ == "__main__":
    main()
