#!/usr/bin/env python3
"""Keep the unit list inside fleet-locator.html in step with the Unit Listing
workbook, without undoing the hand clean-up already in the page.

It compares today's workbook rows (read from a freshly built fleet-status page,
which embeds them) with the rows seen at the last sync (tools/locator-baseline.json)
and applies only real changes: a field edited in the workbook, a new unit, or a
unit removed from the workbook.

usage: python3 tools/refresh_locator.py <built-fleet-status.html> <fleet-locator.html> [units.xlsx]

Coordinates: a unit sits at its town's centre plus a small fixed offset so units
in one town don't stack. Town centres come from units already on the map, plus
tools/locator-geo.json ({"Town name": [lat, lng]}) for towns the map has not seen.
"""
import hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE, GEO_EXTRA = os.path.join(HERE, "locator-baseline.json"), os.path.join(HERE, "locator-geo.json")
EMB = "const EMBEDDED_DATA = "
UNITS_RE = re.compile(r"const UNITS=(\[.*?\]);\n", re.S)
FIELDS = [("region", "region"), ("equipCategory", "catRaw"), ("equipDesc", "desc"), ("org", "org"),
          ("location", "loc"), ("county", "county"), ("contact", "contact")]

norm_id = lambda s: re.sub(r"[^A-Z0-9]", "", str(s or "").upper())
norm_loc = lambda s: re.sub(r"[^a-z0-9]", "", re.sub(r",\s*tx\.?$", "", str(s or "").strip().lower()))
digits = lambda s: re.sub(r"\D", "", str(s or ""))
clean = lambda v: "" if v is None else str(v).strip()

def cat_group(c):
    c = (c or "").lower()
    if "feeding" in c or "church support" in c: return "Feeding"
    if "shower" in c or "laundry" in c: return "Shower/Laundry"
    if "heavy" in c: return "Heavy Equipment"
    if "recovery" in c: return "Recovery"
    if "generator" in c: return "Generator"
    if "manlift" in c or "man lift" in c: return "Manlift"
    if "water" in c: return "Water"
    if "box" in c or "trailer" in c: return "Box / Support"
    if "communication" in c or "electronic" in c: return "Comms / Electronic"
    if "child" in c: return "Child Care"
    if any(w in c for w in ("van", "vehicle", "tractor", "misc", "utv")): return "Vehicle"
    return "Other"

def offset(uid):
    h = int(hashlib.md5(uid.encode()).hexdigest(), 16)
    return ((h % 1000) / 1000 - 0.5) * 0.02, (((h // 1000) % 1000) / 1000 - 0.5) * 0.02

def read_phones(path, known_ids):
    """Best effort: {normalised unit id: phone} from the workbook. Empty if unsure."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        best = {}
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=True))
            for hi, hdr in enumerate(rows[:15]):
                names = [clean(c).lower() for c in hdr]
                pcol = next((i for i, n in enumerate(names) if "phone" in n), -1)
                if pcol < 0: continue
                for icol in range(len(names)):
                    found = {}
                    for r in rows[hi + 1:]:
                        if icol < len(r) and pcol < len(r) and norm_id(r[icol]) in known_ids and clean(r[pcol]):
                            found[norm_id(r[icol])] = clean(r[pcol])
                    if len(found) > len(best): best = found
        return best if len(best) >= 0.3 * len(known_ids) else {}
    except Exception as e:
        print("  note: phone numbers not read from the workbook:", e)
        return {}

def main():
    built_path, page_path = sys.argv[1], sys.argv[2]
    xlsx = sys.argv[3] if len(sys.argv) > 3 else None
    built = open(built_path, encoding="utf-8").read()
    if EMB not in built: sys.exit("ABORT: built fleet-status file has no EMBEDDED_DATA block")
    raw_rows = json.JSONDecoder().raw_decode(built[built.index(EMB) + len(EMB):])[0].get("units") or []
    if len(raw_rows) < 50: sys.exit(f"ABORT: only {len(raw_rows)} unit rows in the built file")
    page = open(page_path, encoding="utf-8").read()
    m = UNITS_RE.search(page)
    if not m or len(UNITS_RE.findall(page)) != 1: sys.exit("ABORT: UNITS block not found exactly once")
    units = json.loads(m.group(1))
    baseline = json.load(open(BASELINE, encoding="utf-8"))          # {locator id: raw workbook row}
    extra_geo = json.load(open(GEO_EXTRA, encoding="utf-8")) if os.path.exists(GEO_EXTRA) else {}

    by_id = {u["id"]: u for u in units}
    centres = {}
    for u in units:
        dy, dx = offset(u["id"])
        centres.setdefault(norm_loc(u["loc"]), (u["lat"] - dy, u["lng"] - dx))
    for name, (lat, lng) in extra_geo.items(): centres.setdefault(norm_loc(name), (lat, lng))

    new_raw = {}
    for r in raw_rows:
        if norm_id(r.get("unitId")): new_raw[norm_id(r["unitId"])] = r
    if sum(1 for b in baseline.values() if norm_id(b.get("unitId")) in new_raw) < 0.5 * len(baseline):
        sys.exit("ABORT: fewer than half of the known units are in today's workbook; not touching the page")
    phones = read_phones(xlsx, set(new_raw)) if xlsx else {}

    log, unknown = [], set()
    def place(u):
        c = centres.get(norm_loc(u["loc"]))
        if not c: unknown.add(u["loc"]); return False
        dy, dx = offset(u["id"])
        u["lat"], u["lng"] = round(c[0] + dy, 5), round(c[1] + dx, 5)
        return True

    # 1. units already on the map
    for loc_id in list(baseline):
        old, u = baseline[loc_id], by_id.get(loc_id)
        new = new_raw.pop(norm_id(old.get("unitId")), None)
        if u is None: del baseline[loc_id]; continue
        if new is None:
            units.remove(u); del baseline[loc_id]; log.append(f"removed {loc_id} (no longer in the workbook)"); continue
        kept = dict(new)
        for raw_key, key in FIELDS:
            if clean(new.get(raw_key)) != clean(old.get(raw_key)):
                before = u.get(key)
                u[key] = clean(new.get(raw_key))
                if key == "catRaw": u["cat"] = cat_group(u["catRaw"])
                if key == "loc" and not place(u):
                    # town not on the map yet: leave the unit where it was and ask again next run
                    u[key] = before; kept[raw_key] = old.get(raw_key); continue
                if key == "contact" and norm_id(new.get("unitId")) not in phones:
                    same = next((x["phone"] for x in units if x is not u and x["contact"] == u["contact"] and x["phone"]), "")
                    u["phone"] = same
                log.append(f"{loc_id}: {key} '{before}' -> '{u[key]}'")
        baseline[loc_id] = kept
        ph = phones.get(norm_id(new.get("unitId")))
        if ph and digits(ph) != digits(u.get("phone")):
            log.append(f"{loc_id}: phone '{u.get('phone')}' -> '{ph}'"); u["phone"] = ph

    # 2. units new to the workbook
    skipped = 0
    for nid, r in new_raw.items():
        if not clean(r.get("location")): skipped += 1; continue
        uid = re.sub(r"\s+", " ", clean(r["unitId"]))
        if uid in by_id: continue
        u = dict(id=uid, region=clean(r.get("region")), cat=cat_group(r.get("equipCategory")), catRaw=clean(r.get("equipCategory")),
                 desc=clean(r.get("equipDesc")), org=clean(r.get("org")), loc=clean(r.get("location")), county=clean(r.get("county")),
                 contact=clean(r.get("contact")), phone=phones.get(nid, ""), lat=0, lng=0)
        if not place(u): continue
        units.append(u); by_id[uid] = u; baseline[uid] = r; log.append(f"added {uid} at {u['loc']}")

    text = json.dumps(units, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out = page[:m.start(1)] + text + page[m.end(1):]
    json.dump(baseline, open(BASELINE, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    if out != page: open(page_path, "w", encoding="utf-8").write(out)
    print(f"fleet-locator: {len(units)} units on the map; changes: {len(log)}; workbook rows without a location skipped: {skipped}")
    for line in log[:60]: print("  ", line)
    if unknown:
        print("NEEDS COORDINATES (add to tools/locator-geo.json as {\"name\": [lat, lng]} and run again):")
        for name in sorted(unknown): print("  ", name)

main()
