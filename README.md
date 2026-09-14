# Sportz Chat FPL

A self-updating Fantasy Premier League stats dashboard for the "Sportz Chat" mini-league,
replacing an old MySQL + Looker Studio pipeline. No server, no database, no cost.

**Live site:** served from `docs/` via GitHub Pages.

## How it works

```
GitHub Actions (hourly)  ->  scripts/update.py  ->  docs/data/*.json  ->  GitHub Pages (docs/)
```

- `scripts/update.py` fetches live data from the public, unauthenticated FPL API,
  merges it with whatever's already committed (an incremental cache for the
  expensive-to-compute bits, e.g. captain results per finished gameweek), computes
  every stat the site shows, and writes it all to `docs/data/*.json`.
- The GitHub Action (`.github/workflows/update.yml`) runs that script every hour
  and commits the result if anything changed. `contents: write` permission on the
  built-in `GITHUB_TOKEN` is all it needs — no secrets, no API keys.
- `docs/` is a plain HTML/CSS/JS site (Chart.js via CDN, no build step) that reads
  those JSON files directly.

### "Jammy" vs the Adjusted Table — two different concepts, don't conflate them

- **Adjusted Table** (`compute_adjusted_table`): a hypothetical — standings re-ranked
  by `total_points + points_on_bench`, i.e. "what if every point you ever left on
  the bench had actually counted." Never really happened; just a what-if.
- **Jammy** (`compute_jammy_leaderboard`): real, already-happened points — the sum of
  what bench players scored when they came on via an FPL **automatic substitution**
  (a starter blanked with 0 minutes, so the game auto-promoted a bench player who
  wasn't meant to start that week). Genuinely unearned, lucky points.

These two used to be conflated (an early version mislabeled the Adjusted Table's
rank-delta as "Jammy"/"Unlucky", which didn't hold up under scrutiny). Autosub data
comes from the FPL API's `automatic_subs` field on the `/entry/{id}/event/{gw}/picks/`
endpoint — the same call already made for captain results, so `fetch_picks_derived()`
extracts both captain and autosub data from one API call per manager per gameweek,
cached incrementally in `docs/data/captains.json` and `docs/data/autosubs.json`
respectively (both keyed manager → finished gameweek, never refetched once cached).

## Changing the league

Edit `docs/data/config.json` -> `league_id`. FPL classic league IDs are **not**
guaranteed stable across seasons for this group (it's changed before) — check the
league's actual ID in the FPL app if standings ever come back empty unexpectedly.

### Tracking someone who isn't in the league (yet, or at all)

`config.json` -> `extra_managers` is `{manager_id: name}` for anyone who should
be tracked everywhere (form, bench, transfers, chips, captaincy, etc.) even
though they have no row in the league's official standings — e.g. someone who
hasn't accepted their invite. Their team name is pulled live from their public
FPL entry. They will **not** appear in the League Table itself (there's no
league rank to show for a non-member), but every other manager-indexed stat
includes them. Remove the entry once they actually join the league — at that
point they'll be picked up normally via standings and the override becomes
redundant (harmless either way, since already-present manager_ids are skipped).

## Historic data

`docs/data/historic.json` holds season-by-season standings from 2013/14 onward,
recovered from an old Google Sheets export. This is **not** re-derivable from the
FPL API once a season ends, so it's seeded once (`scripts/seed_historic.py`) rather
than fetched by the recurring pipeline. It's keyed by manager **name**, not FPL
entry ID — this league's FPL entry IDs have changed at least twice in its history,
but manager names (with `identity.py`'s `NAME_ALIASES` covering one legal name
change) are stable.

Known gap: no 2022/23 row exists for Oliver Dewdney — confirmed genuine (his own
FPL account has no entry for that season either, i.e. he didn't play), not a bug.

`scripts/backfill_historic.py` fills in seasons missing from `historic.json` using
each *current* manager's own FPL entry history (`past` season summaries) — this
group's current manager_ids turned out to be everyone's actual long-standing
personal FPL accounts, so this recovered 2024/25 and 2025/26 in full. Re-run it
whenever there's a new season to catch up on. It also derives each season's total
FPL player count (needed for `overall_percentage`) from existing on-file
(rank, percentage) pairs where possible, falling back to a hardcoded Wikipedia
figure for brand-new seasons with nothing on file yet to derive from — see the
script's docstring for details and caveats (notably: `league_rank` for backfilled
seasons is this friend group's own points ranking among whoever has data, not a
verified reconstruction of an actual league standings snapshot).

## Local development

```
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python3 scripts/update.py   # fetches real live data
cd docs && python3 -m http.server 8791
```

## Deferred / not built yet

- **Predicted points**: `derived.json` has a `predicted_points` placeholder field
  but no logic behind it yet.
- **Consistency** and **Average Position** (Hall of Fame tab) use best-guess
  formulas (stdev of gameweek points; mean league rank) — the original dashboard's
  exact formulas for these two weren't confirmed against real numbers.
