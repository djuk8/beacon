#!/usr/bin/env python3
"""Scan livefire logs for record-worthy finds against the claimed-slot table.

Usage (from the directory containing prime-gap-list/):
    python3 check_records.py                  # scans w*/livefire_log.csv
    python3 check_records.py path1.csv path2.csv

A find is record-worthy if its gap size is unclaimed, or the incumbent's
initiating prime has MORE digits than ours. Finds stay PRIVATE until the
notarization pipeline re-verifies both endpoints and every interior survivor.
Reconstruction: p1 = k * P#(zdesign) + jleft.   Credit handle: djuk8.
"""
import sys, csv, glob, sqlite3

con = sqlite3.connect(":memory:")
con.executescript(open("prime-gap-list/allgaps.sql").read())
claimed = {}
for g, d in con.execute("SELECT gapsize, primedigits FROM gaps WHERE primecat='C'"):
    claimed[g] = min(d, claimed.get(g, 10 ** 9))

paths = sys.argv[1:] or sorted(glob.glob("w*/livefire_log.csv"))
n, hits = 0, []
for p in paths:
    for r in csv.DictReader(open(p)):
        n += 1
        g, D = int(r["gap"]), int(r["D"])
        c = claimed.get(g)
        if c is None or c > D:
            hits.append((g, D, float(r["merit"]), c, r["k"], r["zdesign"],
                         r["jleft"], r["jright"], p))

print(f"scanned {n} trials across {len(paths)} logs -> {len(hits)} RECORD-WORTHY finds\n")
for g, D, m, c, k, zd, jl, jr, p in sorted(hits):
    tag = "VIRGIN SLOT" if c is None else f"beats {c:,}-digit incumbent"
    print(f"  gap {g:>9,}  merit {m:6.3f}  @ {D:,}d  [{tag}]  "
          f"k={k} zd={zd} jl={jl} jr={jr}  ({p})")
if hits:
    print("\nPRIVATE until notarized. Do not submit before the notary pipeline runs.")
