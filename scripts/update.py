#!/usr/bin/env python3
"""
Orchestrator: fetch (with incremental caching) -> compute -> write.
This is what the GitHub Action runs on a schedule. Safe to also run
locally/manually at any time -- it always converges to the same state
for a given point in the season, and never re-does expensive work for
gameweeks it's already cached.
"""
import json
from pathlib import Path

import fetch
import compute

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "docs" / "data"


def write_json(filename, data):
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def load_historic():
    path = DATA_DIR / "historic.json"
    if not path.exists():
        print(f"WARNING: {path} not found -- run scripts/seed_historic.py first.")
        return {}
    with open(path) as f:
        return json.load(f)


def simplify_standings(standings, managers):
    rows = []
    for row in standings["results"]:
        manager_id = str(row["entry"])
        rows.append(
            {
                "manager_id": manager_id,
                "name": managers[manager_id]["name"],
                "team_name": managers[manager_id]["team_name"],
                "rank": row["rank"],
                "event_total": row["event_total"],
                "total": row["total"],
            }
        )
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows


def simplify_players(bootstrap):
    return [
        {
            "id": el["id"],
            "web_name": el["web_name"],
            "team": el["team"],
            "now_cost": el["now_cost"],
            "total_points": el["total_points"],
            "form": el["form"],
            "ep_next": el["ep_next"],  # kept for the deferred predicted-points feature
        }
        for el in bootstrap["elements"]
    ]


def main():
    historic = load_historic()

    print("Fetching live data...")
    fetched = fetch.fetch_all()

    print("Computing derived stats...")
    derived = compute.compute_all(fetched, historic)

    print("Writing output files...")
    write_json("managers.json", fetched["managers"])
    write_json("standings.json", simplify_standings(fetched["standings"], fetched["managers"]))
    write_json(
        "gameweeks.json",
        {k: v for k, v in fetched["gameweeks"].items() if not k.endswith(":chips")},
    )
    write_json("captains.json", fetched["captains"])
    write_json("transfers.json", fetched["transfers"])
    write_json("live_points.json", fetched["live_points"])
    write_json("players.json", simplify_players(fetched["bootstrap"]))
    write_json("derived.json", derived)

    print("Done.")


if __name__ == "__main__":
    main()
