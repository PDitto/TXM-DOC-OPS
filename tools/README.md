# Dashboard refresh tools

These scripts are run by Claude scheduled tasks to keep the dashboards in this
site current. Each one changes only the data inside its page and refuses to
touch the page if the input looks wrong.

| Page | Script | Source of the data | Runs |
| --- | --- | --- | --- |
| `disaster-watch.html` | `sync_disaster_watch.py` | Daily Disaster Watch snapshot refresh | Daily |
| `fleet-status.html` | `publish_fleet_status.py` | Fleet Management and Unit Listing workbooks in Google Drive | Daily |
| `fleet-locator.html` | `refresh_locator.py` | Unit Listing workbook (through the fleet status build) | Daily |
| `dispatch-board.html` | `refresh_dispatch.py` | Rolling Stock Vehicles Google Sheet, first tab | Daily |
| `damage-reports.html` | `build_damage_reports.py` | Web search of news, NWS, TDEM, county and FEMA sources | 07:00 and 19:00 CT |

Notes

- `refresh_locator.py` keeps the hand clean-up already in the map. It applies
  only what changed in the workbook since the last sync, which it remembers in
  `locator-baseline.json`. A unit in a town the map has not seen is left out
  until the town is added to `locator-geo.json` as `{"Town": [lat, lng]}`.
- `refresh_dispatch.py` follows the same rules as the board's own sheet sync:
  it updates status, hitch, weights, model and comments, adds new units and
  never removes one. A unit keeps one row: a sheet number like `B206/#8` is the
  board's `B206`, and a unit renumbered in the sheet (new number in `#`, previous
  one in the first `Old #` column) is renumbered on the board, not added again.
- The dispatch board on this site has no shared database, so assignments made
  here stay in that browser. Only the unit list and statuses are refreshed.
- `build_damage_reports.py` scores each report (damage 45%, impact on living
  35%, media coverage 20%) and ranks the board. The board covers the current
  calendar month only (events that began this month, Central Time) and starts
  fresh on the 1st. A report the latest search did not find stays on for the
  rest of the month. County-to-region codes
  come from `damage-county-regions.json`; the starter entries are best guesses
  and need confirming. The script prints a NOTE for any county not in it.
