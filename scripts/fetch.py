"""
Pulls live data from the FPL API and merges it with whatever's already
cached on disk from previous runs.

Three tiers, per the plan:
  1. Refetched in full every run (cheap): bootstrap, standings, each
     manager's full-season history, raw transfer lists.
  2. Incrementally cached, only extended for gameweeks that have newly
     finished (expensive if done naively): each finished gameweek's
     "live" scores (one call covers every player), captain results.
  3. Static, seeded once: historic.json (untouched here).
"""
import json
from pathlib import Path

import fpl_api
from identity import canonical_name

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "docs" / "data"


def load_json(filename, default):
    path = DATA_DIR / filename
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)


def load_config():
    return load_json("config.json", {})


def fetch_bootstrap():
    return fpl_api.get_bootstrap()


def finished_gameweeks(bootstrap):
    return sorted(
        event["id"] for event in bootstrap["events"] if event.get("finished")
    )


def current_gameweek(bootstrap):
    for event in bootstrap["events"]:
        if event.get("is_current"):
            return event["id"]
    # Between seasons / before GW1: fall back to the highest finished GW.
    finished = finished_gameweeks(bootstrap)
    return finished[-1] if finished else 1


def fetch_standings(league_id):
    return fpl_api.get_standings(league_id)


def managers_from_standings(standings):
    """{manager_id (str): {name, team_name}} built straight from the
    standings payload -- no extra API call needed.

    Falls back to `new_entries` (members who've joined but have no
    ranked row yet) for anyone missing from `results` -- notably the
    normal pre-season state, where nobody has a `standings` row until
    the season's first gameweek completes."""
    managers = {}
    for row in standings["results"]:
        manager_id = str(row["entry"])
        managers[manager_id] = {
            "manager_id": manager_id,
            "name": canonical_name(row["player_name"]),
            "team_name": row["entry_name"],
        }
    for row in standings.get("new_entries", []):
        manager_id = str(row["entry"])
        if manager_id in managers:
            continue
        full_name = f"{row['player_first_name']} {row['player_last_name']}"
        managers[manager_id] = {
            "manager_id": manager_id,
            "name": canonical_name(full_name),
            "team_name": row["entry_name"],
        }
    return managers


def add_extra_managers(managers, extra_managers):
    """Merge in managers who aren't (yet) in the league itself -- e.g.
    someone who hasn't accepted their invite -- so they still show up
    everywhere. `extra_managers` is {manager_id: name} from config.json.
    Team name is fetched live from their public FPL entry."""
    for manager_id, name in (extra_managers or {}).items():
        manager_id = str(manager_id)
        if manager_id in managers:
            continue
        try:
            entry = fpl_api.get_entry(manager_id)
            team_name = entry.get("name", name)
        except RuntimeError:
            team_name = name
        managers[manager_id] = {
            "manager_id": manager_id,
            "name": canonical_name(name),
            "team_name": team_name,
        }
    return managers


def fetch_gameweeks(manager_ids):
    """{manager_id: [{gw, points, total_points, overall_rank, bank,
    value, transfers, transfer_cost, points_on_bench}, ...]}
    Always refetched in full -- the /history/ endpoint returns the
    whole season in one call per manager, so there's nothing to gain
    from trying to cache this incrementally."""
    gameweeks = {}
    for manager_id in manager_ids:
        history = fpl_api.get_entry_history(manager_id)
        gameweeks[manager_id] = [
            {
                "gw": gw["event"],
                "points": gw["points"],
                "total_points": gw["total_points"],
                "overall_rank": gw["overall_rank"],
                "bank": gw["bank"],
                "value": gw["value"],
                "transfers": gw["event_transfers"],
                "transfer_cost": gw["event_transfers_cost"],
                "points_on_bench": gw["points_on_bench"],
            }
            for gw in history["current"]
        ]
        gameweeks[f"{manager_id}:chips"] = history.get("chips", [])
    return gameweeks


def fetch_live_points(finished_gws, cache):
    """{gw (str): {element_id (str): total_points}}. Only fetches
    gameweeks not already present in the cache -- this is the main
    incremental saving, since it replaces what the old pipeline did
    with hundreds of per-player-per-gameweek calls."""
    live_points = dict(cache)
    for gw in finished_gws:
        key = str(gw)
        if key in live_points:
            continue
        data = fpl_api.get_event_live(gw)
        live_points[key] = {
            str(el["id"]): el["stats"]["total_points"] for el in data["elements"]
        }
    return live_points


def fetch_captains(manager_ids, finished_gws, live_points, cache):
    """{manager_id: {gw (str): {captain_points, best_possible_points,
    picked_best_captain, captain_delta}}}. Only computes gameweeks not
    already cached per manager -- captain results for a finished
    gameweek never change, so once cached they're never refetched."""
    captains = {mid: dict(cache.get(mid, {})) for mid in manager_ids}

    for manager_id in manager_ids:
        for gw in finished_gws:
            key = str(gw)
            if key in captains[manager_id]:
                continue

            picks_data = fpl_api.get_picks(manager_id, gw)
            picks = picks_data.get("picks", [])
            gw_points = live_points.get(key, {})

            starters = [p for p in picks if p["position"] <= 11]
            if not starters:
                continue

            captain_pick = next(
                (p for p in picks if p["multiplier"] in (2, 3)), None
            )
            if captain_pick is None:
                continue

            captain_base = gw_points.get(str(captain_pick["element"]), 0)
            captain_points = captain_base * captain_pick["multiplier"]

            best_element, best_base = max(
                ((p["element"], gw_points.get(str(p["element"]), 0)) for p in starters),
                key=lambda pair: pair[1],
            )
            best_possible_points = best_base * captain_pick["multiplier"]

            captains[manager_id][key] = {
                "captain_element": captain_pick["element"],
                "captain_points": captain_points,
                "best_element": best_element,
                "best_possible_points": best_possible_points,
                "picked_best_captain": int(captain_pick["element"] == best_element),
                "captain_delta": captain_points - best_possible_points,
            }

    return captains


def fetch_transfers(manager_ids, live_points, players_by_id):
    """{manager_id: [{gw, player_in, player_in_name, points_in,
    player_out, player_out_name, points_out, net_points}]}. The
    transfer log itself is always refetched (one cheap call per
    manager); net_points is only computable for gameweeks whose live
    scores we have (i.e. finished gameweeks) and is left null
    otherwise until that gameweek completes."""
    transfers_by_manager = {}
    for manager_id in manager_ids:
        raw = fpl_api.get_transfers(manager_id)
        entries = []
        for t in raw:
            gw = t["event"]
            gw_points = live_points.get(str(gw), {})
            points_in = gw_points.get(str(t["element_in"]))
            points_out = gw_points.get(str(t["element_out"]))
            net_points = (
                points_in - points_out
                if points_in is not None and points_out is not None
                else None
            )
            entries.append(
                {
                    "gw": gw,
                    "time": t["time"],
                    "player_in": t["element_in"],
                    "player_in_name": players_by_id.get(t["element_in"], "?"),
                    "points_in": points_in,
                    "player_out": t["element_out"],
                    "player_out_name": players_by_id.get(t["element_out"], "?"),
                    "points_out": points_out,
                    "net_points": net_points,
                }
            )
        transfers_by_manager[manager_id] = entries
    return transfers_by_manager


def fetch_all():
    config = load_config()
    league_id = config["league_id"]

    bootstrap = fetch_bootstrap()
    finished_gws = finished_gameweeks(bootstrap)
    players_by_id = {el["id"]: el["web_name"] for el in bootstrap["elements"]}

    standings = fetch_standings(league_id)
    managers = managers_from_standings(standings)
    managers = add_extra_managers(managers, config.get("extra_managers"))
    manager_ids = list(managers.keys())

    gameweeks = fetch_gameweeks(manager_ids)

    live_points_cache = load_json("live_points.json", {})
    live_points = fetch_live_points(finished_gws, live_points_cache)

    captains_cache = load_json("captains.json", {})
    captains = fetch_captains(manager_ids, finished_gws, live_points, captains_cache)

    transfers = fetch_transfers(manager_ids, live_points, players_by_id)

    return {
        "config": config,
        "bootstrap": bootstrap,
        "standings": standings,
        "managers": managers,
        "gameweeks": gameweeks,
        "live_points": live_points,
        "captains": captains,
        "transfers": transfers,
        "players_by_id": players_by_id,
    }
