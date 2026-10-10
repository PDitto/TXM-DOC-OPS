#!/usr/bin/env python3
"""Publish a freshly built Fleet & Unit Status dashboard as fleet-status.html,
after checking that it really is that dashboard and carries data.

usage: python3 tools/publish_fleet_status.py <built.html> <fleet-status.html>
"""
import json, sys

MARK = "const EMBEDDED_DATA = "

def embedded(text, name):
    if MARK not in text:
        sys.exit(f"ABORT: {name} has no EMBEDDED_DATA block")
    data, _ = json.JSONDecoder().raw_decode(text[text.index(MARK) + len(MARK):])
    return data

def main():
    src_path, page_path = sys.argv[1], sys.argv[2]
    src = open(src_path, encoding="utf-8").read()
    data = embedded(src, "built file")
    fleet, units = data.get("fleet") or [], data.get("units") or []
    if "Fleet" not in src[:4000] or len(fleet) < 50 or len(units) < 50:
        sys.exit(f"ABORT: built file looks wrong (fleet rows {len(fleet)}, unit rows {len(units)})")
    old = open(page_path, encoding="utf-8").read()
    if old == src:
        print("fleet-status: no change")
        return
    open(page_path, "w", encoding="utf-8").write(src)
    print(f"fleet-status: published, generated {data.get('generatedAt')}, {len(fleet)} vehicles, {len(units)} units")

main()
