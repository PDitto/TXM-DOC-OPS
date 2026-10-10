# Dashboard refresh tools

These scripts are run by Claude scheduled tasks to keep the dashboards in this
site current. Each one changes only the data inside its page and refuses to
touch the page if the input looks wrong.

| Page | Script | Source of the data | Runs |
| --- | --- | --- | --- |
| `Hurricane Isaias.html` | (script kept in the task) | Hourly news, outage and NHC pull | Hourly |
| `disaster-watch.html` | `sync_disaster_watch.py` | Daily Disaster Watch snapshot refresh | Daily |
| `fleet-status.html` | `publish_fleet_status.py` | Fleet Management and Unit Listing workbooks in Google Drive | Daily |
| `fleet-locator.html` | `refresh_locator.py` | Unit Listing workbook (through the fleet status build) | Daily |
| `dispatch-board.html` | `refresh_dispatch.py` | Rolling Stock Vehicles Google Sheet, first tab | Daily |

Notes

- `refresh_locator.py` keeps the hand clean-up already in the map. It applies
  only what changed in the workbook since the last sync, which it remembers in
  `locator-baseline.json`. A unit in a town the map has not seen is left out
  until the town is added to `locator-geo.json` as `{"Town": [lat, lng]}`.
- `refresh_dispatch.py` follows the same rules as the board's own sheet sync:
  it updates status, hitch, weights, model and comments, adds new units and
  never removes one.
- The dispatch board on this site has no shared database, so assignments made
  here stay in that browser. Only the unit list and statuses are refreshed.
