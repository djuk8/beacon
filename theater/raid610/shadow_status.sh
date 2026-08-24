#!/bin/bash
# shadow_status.sh -- read the feeder ledger: rings, windows/s, test ratio, per rung, last N minutes; plus loop health. Read-only.
C=${C:-0}; M=${M:-10}; R=$HOME/beacon/raid610
python3 - "$R/queue/c$C/ledger.jsonl" "$M" <<'PY'
import sys, json, time, collections
p, m = sys.argv[1], float(sys.argv[2]); t0 = time.time() - m*60; by = collections.defaultdict(lambda: [0,0,0,0]); first = None
for l in open(p):
    d = json.loads(l)
    if d["ts"] < t0: continue
    first = min(first or d["ts"], d["ts"]); r = by[int(d["round"])]; r[0]+=1; r[1]+=d["ks"]; r[2]+=d["n"]; r[3]+=d["tested"]
span = max(1, time.time() - (first or time.time()))
print(f"last {m:.0f} min (span {span/60:.1f} min):"); tt=tn=0
for k in sorted(by):
    n, ks, nn, te = by[k]; tt+=te; tn+=nn; print(f"  r{k:02d}: rings {n:5d}  ks {ks:9,}  cands {nn:11,}  tested {te:11,} ({te/max(nn,1):.3f})")
r1 = by.get(1, [0,0,0,0]); print(f"  rung-1 windows/s this card: {r1[1]/span:,.0f}   (legacy box-wide reference ~3,600/card)   tests/s this card: {tt/span:,.0f}   overall test ratio {tt/max(tn,1):.3f}")
PY
echo "loops alive: $(pgrep -fc raid_loop_v2.sh)  feeder: $(pgrep -fc "ee_serve.py --queue $R/queue/c$C ")  queue req/claimed/failed: $(ls $R/queue/c$C/req | wc -l)/$(ls $R/queue/c$C/claimed | wc -l)/$(ls $R/queue/c$C/failed 2>/dev/null | wc -l)"
new=$(tac $R/queue/c$C/log_offsets.txt 2>/dev/null | sort -u -k1,1 | while read s off; do [ -f $R/hunt_s$s.log ] && tail -c +$((off+1)) $R/hunt_s$s.log; done)
echo "since latest (re)start -- FEEDER warnings: $(echo "$new" | grep -c FEEDER)   DRIVE/FOLD FAIL: $(echo "$new" | grep -cE 'DRIVE FAIL|FOLD FAIL')   DRIVE RETRY: $(echo "$new" | grep -c 'DRIVE RETRY')   finish.log written last ${M}m by $(find $R/hunt_s*/finish.log -mmin -$M 2>/dev/null | wc -l) seeds"
tail -2 $R/feeder_c$C.log
