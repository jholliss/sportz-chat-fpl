#!/usr/bin/env python3
"""
One-off seed script. NOT part of the recurring update workflow.

Converts the recovered Google Sheets export
"SportzChatFantasyFootballData - HistoricData.csv" (season-by-season
standings, 2013/14-2023/24 -- the one dataset that can't be re-derived
from the live FPL API once a season has closed) into docs/data/historic.json.

IMPORTANT: keyed by manager NAME, not manager_id. The source data shows
manager_id is NOT stable across this history -- the group's FPL entry IDs
changed at some point (e.g. James Holliss is manager_id 1106667 for
2013/14-2020/21 but 630247 for 2023/24), and two seasons (2021/22,
2022/23) have no manager_id recorded at all. Name is the only field
that's consistently present and correct across every row. The live
pipeline joins this to the current season by manager name.

One manager legally changed their name (James Petrie -> James Wiles for
a stretch of seasons, then back to James Petrie). NAME_ALIASES below
merges known aliases onto one canonical name so history isn't split
across two people.

Run once, locally:
    python3 scripts/seed_historic.py /path/to/HistoricData.csv

Re-run any time the source CSV is updated (e.g. a future season gets
manually appended to it) to regenerate historic.json from scratch.
"""
import csv
import json
import sys
from pathlib import Path

from identity import canonical_name

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "docs" / "data" / "historic.json"


def parse_float(value):
    value = (value or "").strip()
    if not value:
        return None
    return float(value)


def parse_int(value):
    value = (value or "").strip()
    if not value:
        return None
    return int(float(value))


def load_historic(csv_path):
    """Returns {manager_name: [{year, points, overall_rank,
    overall_percentage, league_rank, manager_id}, ...]} sorted by year.

    manager_id is carried through per-season (it's what was recorded that
    year, may be None) but the dict key -- and the join key the live
    pipeline uses -- is the manager's name."""
    by_manager = {}

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Player") or "").strip()
            if not name:
                continue
            name = canonical_name(name)

            entry = {
                "year": (row.get("Year") or "").strip(),
                "points": parse_int(row.get("Points")),
                "overall_rank": parse_int(row.get("OverallRank")),
                "overall_percentage": parse_float(row.get("OverallPercentage")),
                "league_rank": parse_int(row.get("LeagueRank")),
                "manager_id": (row.get("manager_id") or "").strip() or None,
            }
            by_manager.setdefault(name, []).append(entry)

    for name, seasons in by_manager.items():
        seasons.sort(key=lambda s: s["year"])

    return by_manager


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-HistoricData.csv>")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    historic = load_historic(csv_path)

    total_rows = sum(len(seasons) for seasons in historic.values())
    print(f"Parsed {total_rows} season rows across {len(historic)} managers.")
    for name, seasons in historic.items():
        years = ", ".join(s["year"] for s in seasons)
        print(f"  {name}: {years}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(historic, f, indent=2)
        f.write("\n")

    print(f"\nWrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
