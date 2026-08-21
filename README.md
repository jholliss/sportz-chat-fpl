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

Known gap: no 2022/23 row exists for Oliver Dewdney in the source data — genuine
gap in the original sheet, not a bug in the seeding script.

To add a future season once it's no longer live-trackable via the API, append rows
to the source CSV and re-run `scripts/seed_historic.py`.

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
