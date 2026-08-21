"""
Thin wrapper around the public, unauthenticated Fantasy Premier League API.

No API key is needed for any of these endpoints. They're all read-only GETs
against fantasy.premierleague.com. A plain requests.Session with a real
User-Agent and small retry/backoff is enough -- no auth, no secrets.
"""
import time

import requests

BASE_URL = "https://fantasy.premierleague.com/api"

_session = requests.Session()
_session.headers.update(
    {
        # FPL's API has been known to 403 requests with no User-Agent.
        "User-Agent": "sportz-chat-fpl-bot/1.0 (+https://github.com/)",
    }
)


def _get(path, **params):
    url = f"{BASE_URL}{path}"
    last_error = None
    for attempt in range(3):
        try:
            response = _session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"FPL API request failed for {url}: {last_error}") from last_error


def get_bootstrap():
    """All players, all gameweeks (events), teams, total_players."""
    return _get("/bootstrap-static/")


def get_standings(league_id):
    """Classic league standings. Handles pagination (only matters for
    leagues with 50+ entries, but cheap to support properly).

    Also returns `new_entries` -- members who have joined the league but
    have no `standings` row yet. That's the normal state before the
    season's first gameweek has completed (FPL only populates
    `standings.results` once there's a score to rank), so it's needed
    as a fallback source of "who's in this league" pre-season."""
    all_results = []
    page = 1
    league_meta = None
    new_entries = []
    while True:
        data = _get(f"/leagues-classic/{league_id}/standings/", page_standings=page)
        league_meta = data.get("league", league_meta)
        standings = data.get("standings", {})
        all_results.extend(standings.get("results", []))
        if page == 1:
            new_entries = data.get("new_entries", {}).get("results", [])
        if not standings.get("has_next"):
            break
        page += 1
    return {"league": league_meta, "results": all_results, "new_entries": new_entries}


def get_entry_history(manager_id):
    """Full season gameweek-by-gameweek history for a manager, plus
    `past` (prior season summaries, per this FPL account) and `chips`
    (chip name + event used)."""
    return _get(f"/entry/{manager_id}/history/")


def get_picks(manager_id, gw):
    """A manager's picks for one gameweek. Includes `multiplier`
    (2=captain, 3=triple captain) and `active_chip`."""
    return _get(f"/entry/{manager_id}/event/{gw}/picks/")


def get_element_summary(player_id):
    """A player's full-season per-gameweek stats (`history`)."""
    return _get(f"/element-summary/{player_id}/")


def get_event_live(gw):
    """Every player's stats for a single gameweek, in one call
    (`elements`: [{id, stats: {total_points, ...}}]). Far cheaper than
    calling get_element_summary() per player when all we need is one
    gameweek's points for many players (captain comparisons, transfer
    effectiveness)."""
    return _get(f"/event/{gw}/live/")


def get_transfers(manager_id):
    """Full transfer history for a manager: element_in, element_out,
    event (gw), time, per transfer."""
    return _get(f"/entry/{manager_id}/transfers/")
