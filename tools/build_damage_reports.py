#!/usr/bin/env python3
"""Score and publish Texas damage reports into damage-reports.html.

usage: python3 tools/build_damage_reports.py <reports.json> damage-reports.html

<reports.json> is what a refresh run found:
  {"captured": "2026-11-17T13:00:00Z",
   "reports": [ { ...one object per disaster event, fields below... } ]}

Only the block between the "// <<DATA" and "// DATA>>" lines of the page is
changed. The board covers one calendar month (Central Time): only events whose
event_date falls in the month of `captured` are kept, so on the 1st the board
starts fresh. Reports already on the board that this run did not find are kept
for the rest of the month, so a thin search never empties the board.

Report fields (unknown numbers: leave out or null, never guess):
  id            short stable slug, same every run for the same event, e.g. "elpaso-flood-2026-10"
  title         short headline
  hazard        flood | tornado | wind | hail | wildfire | winter | tropical | other
  status        response | recovery | monitoring
  event_date    YYYY-MM-DD the event began
  updated       YYYY-MM-DD of the newest source used
  place         city/community
  counties      list of county names (no "County")
  lat, lon      point for the map (city centre is fine)
  homes         {"destroyed","major","minor","affected"}  affected = damaged, severity not given
  damage_usd    official dollar estimate
  declaration   none | local | state | sba | federal  (highest reached or requested+approved)
  deaths, injuries, rescues, displaced (people), power_out (customers), shelters (open)
  boil_water, roads_closed   true/false
  media         {"outlets": distinct outlets covering it, "national": true if national outlet}
  summary       1-2 sentences, own words
  txm_angle     what TXM DR might bring (mud-out, chainsaw, feeding, ...), short
  sources       [{"title","url"}]
"""
import json, math, re, sys
from datetime import datetime, timezone, timedelta

BLOCK = re.compile(r'(// <<DATA\n)(.*?)(\n// DATA>>)', re.S)
HAZARDS = {"flood", "tornado", "wind", "hail", "wildfire", "winter", "tropical", "other"}
STATUS = {"response", "recovery", "monitoring"}
DECL = {"none": 0, "local": 3, "state": 8, "sba": 11, "federal": 15}
CENTRAL = timedelta(hours=-6)  # month boundary in Central Standard Time


def num(v):
    try:
        return max(0.0, float(v)) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def lg(x):
    return math.log10(1 + x)


def score(r):
    h = r.get("homes") or {}
    pts = 10 * num(h.get("destroyed")) + 5 * num(h.get("major")) + 2 * num(h.get("minor")) + num(h.get("affected"))
    homes = min(85, 22 * lg(pts))
    usd = num(r.get("damage_usd"))
    dollars = min(85, 20 * math.log10(usd / 1e5)) if usd >= 1e5 else 0
    damage = min(100, max(homes, dollars) + DECL.get(r.get("declaration") or "none", 0))

    life = min(35, 12 * num(r.get("deaths")) + 2 * num(r.get("injuries")) + 8 * lg(num(r.get("rescues"))))
    displaced = min(30, 12 * lg(num(r.get("displaced"))))
    utilities = min(20, 5 * lg(num(r.get("power_out"))) + (8 if r.get("boil_water") else 0))
    access = (5 if r.get("roads_closed") else 0) + min(10, 5 * num(r.get("shelters")))
    living = min(100, life + displaced + utilities + access)

    m = r.get("media") or {}
    media = min(100, 35 * lg(num(m.get("outlets"))) + (25 if m.get("national") else 0))

    pri = 0.45 * damage + 0.35 * living + 0.20 * media
    tier = "critical" if pri >= 60 else "high" if pri >= 40 else "moderate" if pri >= 20 else "watch"
    return {"damage": round(damage), "living": round(living), "media": round(media),
            "priority": round(pri), "tier": tier}


def check(r):
    for k in ("id", "title", "hazard", "status", "event_date", "updated", "lat", "lon"):
        if r.get(k) in (None, ""):
            return f"missing {k}"
    if r["hazard"] not in HAZARDS:
        return f"hazard '{r['hazard']}' not one of {sorted(HAZARDS)}"
    if r["status"] not in STATUS:
        return f"status '{r['status']}' not one of {sorted(STATUS)}"
    if (r.get("declaration") or "none") not in DECL:
        return f"declaration '{r.get('declaration')}' not one of {list(DECL)}"
    try:
        datetime.strptime(r["event_date"], "%Y-%m-%d"); datetime.strptime(r["updated"], "%Y-%m-%d")
        lat, lon = float(r["lat"]), float(r["lon"])
    except (ValueError, TypeError) as e:
        return f"bad date or coordinate ({e})"
    if not (25.5 <= lat <= 36.7 and -106.8 <= lon <= -93.4):
        return f"point {lat},{lon} is outside Texas"
    return None


def main():
    src_path, page_path = sys.argv[1], sys.argv[2]
    found = json.load(open(src_path, encoding="utf-8"))
    page = open(page_path, encoding="utf-8").read()
    m = BLOCK.search(page)
    if not m:
        sys.exit("ABORT: page has no // <<DATA ... // DATA>> block")
    try:
        old = json.loads(m.group(2).strip()[len("const DATA = "):].rstrip(";"))
    except Exception as e:
        sys.exit(f"ABORT: could not read the page's current data ({e})")
    try:
        captured = datetime.strptime(found["captured"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        sys.exit("ABORT: 'captured' must look like 2026-11-17T13:00:00Z")

    regions = json.load(open("tools/damage-county-regions.json", encoding="utf-8"))
    regions = {k.lower(): v for k, v in regions.items() if not k.startswith("_")}
    prev = {r["id"]: r for r in old.get("reports", [])}
    local = captured + CENTRAL
    month = (local.year, local.month)

    out, seen, problems = [], set(), []
    for r in found.get("reports", []):
        err = check(r)
        if err:
            problems.append(f"skipped '{r.get('title', r.get('id'))}': {err}")
            continue
        if r["id"] in seen:
            problems.append(f"skipped duplicate id {r['id']}")
            continue
        seen.add(r["id"])
        r["carried"] = False
        out.append(r)
    for rid, r in prev.items():
        if rid not in seen:
            r = dict(r); r["carried"] = True
            out.append(r)

    kept = []
    for r in out:
        ev = datetime.strptime(r["event_date"], "%Y-%m-%d")
        if (ev.year, ev.month) != month:
            print(f"left off (began {r['event_date']}, outside {local:%B %Y}): {r['title']}")
            continue
        p = prev.get(r["id"])
        sc = score(r)
        r.update(sc)
        r["is_new"] = p is None
        r["change"] = 0 if p is None else sc["priority"] - p.get("priority", sc["priority"])
        regs = sorted({regions[c.lower()] for c in r.get("counties", []) if c.lower() in regions})
        missing = [c for c in r.get("counties", []) if c.lower() not in regions]
        if missing:
            problems.append(f"no TXM region on file for: {', '.join(missing)}")
        r["regions"] = regs
        kept.append(r)
    kept.sort(key=lambda r: (-r["priority"], r["title"]))

    data = {"captured": found["captured"], "month": f"{local:%B %Y}", "reports": kept}
    new_block = "const DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";"
    page2 = page[:m.start(2)] + new_block + page[m.end(2):]
    open(page_path, "w", encoding="utf-8").write(page2)

    print(f"damage-reports: {len(kept)} reports, captured {found['captured']}")
    for r in kept:
        flag = "NEW " if r["is_new"] else ("kept" if r["carried"] else "upd ")
        print(f"  {flag} {r['priority']:>3} {r['tier']:<8} {r['title']}")
    for p in problems:
        print("NOTE:", p)


main()
