#!/usr/bin/env python3
"""claimcheck_v1.py -- compare walked gaps (ledger lines: gap merit k jl jr ts rung) against the per-gap-size record table (arbitrage_map_v0.csv).
A find CLAIMS a gap size when its merit exceeds the table's current merit for that exact gap size (the parade rule)."""
import csv, sys, collections
ledger, table = sys.argv[1], sys.argv[2]
rec = {}
for r in csv.DictReader(open(table)): rec[int(r["gapsize"])] = float(r["current_merit"])
finds = []
for ln in open(ledger):
    f = ln.split()
    if len(f) < 5: continue
    try: gap, merit = int(f[0]), float(f[1])
    except ValueError: continue
    finds.append((gap, merit, f[2], f[3], f[4]))
finds.sort(reverse=True)
print(f"{len(finds)} walked gaps in ledger; table covers {len(rec):,} gap sizes")
claims = [(g, m, k, jl, jr, rec.get(g)) for g, m, k, jl, jr in finds if g in rec and m > rec[g]]
print(f"CLAIMS (merit beats the table for that gap size): {len(claims)}")
for g, m, k, jl, jr, cur in claims[:40]: print(f"  gap {g:>7}  merit {m:8.4f}  beats {cur:7.4f}  k={k} jl={jl} jr={jr}")
by = collections.Counter(int(m) for g, m, *_ in finds); print("merit histogram:", dict(sorted(by.items(), reverse=True)))
print("top 10 by merit:"); [print(f"  gap {g:>7} merit {m:8.4f} k={k}") for g, m, k, *_ in sorted(finds, key=lambda x: -x[1])[:10]]
