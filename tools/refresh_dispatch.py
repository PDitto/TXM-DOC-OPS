#!/usr/bin/env python3
"""Refresh the built-in rolling stock list inside dispatch-board.html from a CSV
export of the "Current Rolling Stock" tab of the Rolling Stock Vehicles sheet.
Mirrors the page's own live sync (syncRollingStock): existing units get their
status, hitch, weights, model and comments from the sheet; units the board has
never seen are added; nothing is removed.

usage: python3 tools/refresh_dispatch.py <rolling-stock.csv> <dispatch-board.html>
"""
import csv, io, json, re, sys

MARK = "const ROLLING_STOCK_ASSETS = "
slug = lambda s: re.sub(r"[^a-z0-9]+", "", str(s).lower())

def bucket(status):
    s = str(status or "").strip().lower()
    if not s or s in ("available", "active"): return "available"
    if s == "deployed": return "deployed"
    if s in ("out of service", "oos", "decommissioned") or s.startswith("dissolved"): return "oos"
    return "assigned"

def parse_sheet(text):
    rows = list(csv.reader(io.StringIO(text)))
    if not rows: return None
    hdr = [c.strip().upper() for c in rows[0]]
    col = lambda name: hdr.index(name) if name in hdr else -1
    uc, sc = col("#"), col("STATUS")
    if uc < 0 or sc < 0: return None
    mc, tc, cc, yc, mk, md, hc, ec, gc = (col(n) for n in
        ("MINISTRY AREA", "TYPE", "COMMENTS", "YEAR", "MAKE", "MODEL", "HITCH", "EMPTY WEIGHT", "GVWR"))
    cell = lambda r, i: str(r[i]).strip() if 0 <= i < len(r) else ""
    def weight(r, i):
        digits = re.sub(r"[^0-9]", "", cell(r, i))
        n = int(digits) if digits else 0
        return n if n > 100 else None
    units = {}
    for r in rows[1:]:
        unit = cell(r, uc)
        if not unit or unit == "#": continue
        ymm = " ".join(x for x in (cell(r, yc), cell(r, mk), cell(r, md)) if x)
        units[unit] = dict(status=cell(r, sc), area=cell(r, mc), type=cell(r, tc),
            desc=" — ".join(x for x in (ymm, cell(r, cc)) if x),
            model=cell(r, md), comments=cell(r, cc), hitch=cell(r, hc), ew=weight(r, ec), gvwr=weight(r, gc))
    return units or None

def kind_for(info):
    t = (info["type"] or "").lower()
    if "equipment" in t: return "equipment"
    if "trailer" in t: return "trailer"
    if "vehicle" in t or "truck" in t: return "truck"
    return "trailer"

def category_for(unit, info):
    if re.search(r"\bRB\b|rebuild", unit + " " + (info["desc"] or ""), re.I): return "Rebuild"
    return "DR" if (info["area"] or "").strip().upper() == "DR" else "Other"

def main():
    csv_path, page_path = sys.argv[1], sys.argv[2]
    units = parse_sheet(open(csv_path, encoding="utf-8-sig").read())
    if not units:
        sys.exit("ABORT: sheet layout not recognised (need '#' and 'STATUS' columns in the first row)")
    page = open(page_path, encoding="utf-8").read()
    if page.count(MARK) != 1:
        sys.exit("ABORT: ROLLING_STOCK_ASSETS block not found exactly once")
    start = page.index(MARK) + len(MARK)
    assets, n = json.JSONDecoder().raw_decode(page[start:])
    by_slug = {slug(a["unit"]): a for a in assets}
    matched = sum(1 for u in units if slug(u) in by_slug)
    if matched < 0.5 * len(assets):
        sys.exit(f"ABORT: only {matched} of {len(assets)} board units found in the sheet; not touching the page")
    changed, added = [], []
    for unit, info in units.items():
        raw = info["status"] or "Available"
        a = by_slug.get(slug(unit))
        if a:
            new = dict(status=raw, oos=bucket(raw) == "oos", hitch=info["hitch"] or "",
                       ew=info["ew"], gvwr=info["gvwr"], m=info["model"] or "", c=info["comments"] or "")
            if any(a.get(k) != v for k, v in new.items()):
                if a.get("status") != raw: changed.append(f"{a['unit']}: {a.get('status')} -> {raw}")
                a.update(new)
        else:
            kind = kind_for(info)
            a = dict(unit=unit, kind=kind, category=category_for(unit, info), description=info["desc"] or "",
                     oos=bucket(raw) == "oos", status=raw, hitch=info["hitch"] or "", ew=info["ew"],
                     gvwr=info["gvwr"], m=info["model"] or "", c=info["comments"] or "")
            assets.append(a); by_slug[slug(unit)] = a; added.append(unit)
    text = json.dumps(assets, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out = page[:start] + text + page[start + n:]
    if out == page:
        print("dispatch-board: no change"); return
    open(page_path, "w", encoding="utf-8").write(out)
    print(f"dispatch-board: {len(assets)} units; status changes: {len(changed)}; added: {len(added)}")
    for line in changed[:40]: print("  ", line)
    for unit in added[:40]: print("   added", unit)

main()
