#!/usr/bin/env python3
"""claims_live.py -- which of your walked gaps improve the Prime Gap List, as paste-ready submission lines.
  git clone --depth 1 https://github.com/primegap-list-project/prime-gap-list pgl      (or git -C pgl pull: always check a fresh list)
  python3 claims_live.py ~/beacon/raid610/campaign_ledger.log pgl/allgaps.sql [--min-merit 30] [--out claims.txt]
Ledger lines (crown venue): gap merit k jl jr ...  -> best find per gap size; a line is printed when its merit beats the list's entry for that
size (or the size is empty). Output: 'gap merit k*1439#/2310-|jl|', the portal's format. Then re-derive them from k before pasting:
  awk '{split($3,a,"*"); print a[1], $2}' claims.txt > ks.txt && python3 rewalk.py ks.txt   (the server re-verifies everything anyway)"""
import argparse, re, sys
ap = argparse.ArgumentParser(); ap.add_argument("ledger"); ap.add_argument("allgaps"); ap.add_argument("--min-merit", type=float, default=0.0)
ap.add_argument("--out", default="claims.txt"); a = ap.parse_args()
R = re.compile(r"^INSERT INTO gaps VALUES\((\d+),\d+,'[^']*','[^']*','[^']*','([^']*)',-?\d+,([0-9.]+),")
cur = {}
for ln in open(a.allgaps):
    m = R.match(ln)
    if m: cur[int(m.group(1))] = (float(m.group(3)), m.group(2))
if not cur: sys.exit("no rows read from " + a.allgaps)
best = {}
for ln in open(a.ledger):
    f = ln.split()
    try: g, mer, k, jl = int(f[0]), float(f[1]), int(f[2]), int(f[3])
    except (ValueError, IndexError): continue
    if mer >= a.min_merit and (g not in best or mer > best[g][0]): best[g] = (mer, k, jl)
out = sorted(((mer, g, k, jl) for g, (mer, k, jl) in best.items() if g not in cur or mer > cur[g][0]), reverse=True)
with open(a.out, "w") as fo:
    for mer, g, k, jl in out: fo.write(f"{g} {mer:.4f} {k}*1439#/2310{jl:+d}\n")
print(f"list: {len(cur):,} sizes | ledger: {len(best):,} sizes at merit >= {a.min_merit} | claims: {len(out):,} -> {a.out}")
for mer, g, k, jl in out[:10]: print(f"  {g} {mer:.4f} {k}*1439#/2310{jl:+d}   (list: {cur.get(g, ('-', 'empty'))[0]} {cur.get(g, ('', ''))[1]})")
