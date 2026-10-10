#!/usr/bin/env python3
"""Copy the snapshot (CAPTURED + SNAP) from a freshly refreshed Disaster Watch
page into the published disaster-watch.html. Nothing else in the page changes.

usage: python3 tools/sync_disaster_watch.py <refreshed.html> <disaster-watch.html>
"""
import re, sys

CAP = re.compile(r'const CAPTURED = "[^"\n]*";')
SNAP = re.compile(r'const SNAP = \{.*?\n\};', re.S)

def parts(text, name):
    c, s = CAP.findall(text), SNAP.findall(text)
    if len(c) != 1 or len(s) != 1:
        sys.exit(f"ABORT: {name}: expected one CAPTURED line and one SNAP block, found {len(c)} and {len(s)}")
    return c[0], s[0]

def main():
    src_path, page_path = sys.argv[1], sys.argv[2]
    src = open(src_path, encoding="utf-8").read()
    page = open(page_path, encoding="utf-8").read()
    cap, snap = parts(src, "refreshed file")
    parts(page, "published page")
    for key in ("hurricanes", "firesUS", "quakes", "fema"):
        if key + ":" not in snap:
            sys.exit(f"ABORT: refreshed SNAP has no '{key}' section")
    out = CAP.sub(lambda m: cap, page, count=1)
    out = SNAP.sub(lambda m: snap, out, count=1)
    if out == page:
        print("disaster-watch: no change")
        return
    open(page_path, "w", encoding="utf-8").write(out)
    print("disaster-watch: snapshot now", cap)

main()
