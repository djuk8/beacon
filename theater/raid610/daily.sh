#!/bin/bash
# daily.sh -- the campaign's daily read: throughput, fossil audit, harvest, ledger, claims, incidents, box health. Usage: bash ~/beacon/p3/o1_kit/daily.sh [hours=24]
H=${1:-24}; R=/root/beacon/raid610; cd $R || exit 1
echo "=== BEACON daily read  $(date -u +%FT%TZ)  (last $H h) ==="
/venv/main/bin/python3 - "$H" <<'PY'
import json, time, glob, os, collections, sys
H = int(sys.argv[1]); now = time.time(); S = 4 * 3600; W = {}; r7t = collections.Counter(); r8t = collections.Counter()
for c in [d[1:] for d in sorted(os.listdir('queue')) if d.startswith('c')] if os.path.isdir('queue') else []:
    p = f'queue/c{c}/ledger.jsonl'
    if not os.path.exists(p): continue
    with open(p, 'rb') as f:
        try: f.seek(-1_200_000_000, 2)
        except OSError: f.seek(0)
        f.readline()
        for ln in f:
            try: d = json.loads(ln)
            except Exception: continue
            if d['ts'] < now - H * 3600: continue
            k = int((now - d['ts']) // S); r = int(d['round'])
            if r == 1: s = W.setdefault(k, [0, 0, 0]); s[0] += d['ks']; s[1] += d['tested']; s[2] += int(d.get('survivors', 0))
            elif r == 7: r7t[k] += d['ks']
            elif r == 8: r8t[k] += d['ks']
land = collections.Counter()
for mf in glob.glob('walked/**/sc_r07_*.manifest.json', recursive=True) + glob.glob('hunt_s1*/sc_r07_*.manifest.json'):
    age = now - os.path.getmtime(mf)
    if age < H * 3600:
        try: land[int(age // S)] += len(json.load(open(mf))['ks'])
        except Exception: pass
print("hours ago     w/s    t/w   pass1  | r7 tested  r7 landed  r8 tested")
tot = 0
for k in sorted(W):
    a, b, c = W[k]; tot += a
    print(f"  {k*4:>2}-{k*4+4:<2}   {a/S:7,.0f}  {b/max(a,1):5.1f}  {c/max(a,1):.4f} |   {r7t[k]:5}      {land[k]:5}      {r8t[k]:4}")
print(f"windows in window: {tot:,}   mean w/s {tot/(H*3600):,.0f}   crown-effective {tot/(H*3600)*1.42:,.0f}")
PY
echo "--- harvest ---"; tail -2 harvest.log 2>/dev/null | cut -c1-120
echo "--- ledger ---"; [ -f campaign_ledger.log ] || { echo "no ledger yet (no walks on this box)"; exit 0; }; echo ""; L=$(wc -l < campaign_ledger.log 2>/dev/null || echo 0); T=$(date -u -d "$H hours ago" +%FT%TZ)
NEW=$(awk -v t="$T" '$6 > t' campaign_ledger.log 2>/dev/null); echo "walked total $L | new in window: $(echo "$NEW" | grep -c .) | >=30: $(echo "$NEW" | awk '$2>=30' | grep -c .) | >=32: $(echo "$NEW" | awk '$2>=32' | grep -c .) | >=36: $(echo "$NEW" | awk '$2>=36' | grep -c .)"
echo "best new:"; echo "$NEW" | sort -k2 -gr | head -3 | awk '{printf "    gap %s merit %s k=%s (%s)\n", $1, $2, $3, $7}'
echo "all-time top:"; sort -k2 -gr campaign_ledger.log 2>/dev/null | head -3 | awk '{printf "    gap %s merit %s k=%s %s\n", $1, $2, $3, substr($6,1,10)}'
/venv/main/bin/python3 /root/beacon/p3/o1_kit/claimcheck_v1.py campaign_ledger.log arbitrage_map_v0.csv 2>/dev/null | sed -n 2p
echo "--- box ---"; echo "load $(cut -d' ' -f1-3 /proc/loadavg) | gpu $(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | tr '\n' ' ')| managers $(pgrep -fc 'ladder.py --card') feeders $(pgrep -fc '^/venv/main/bin/python3 /root/beacon/p3/ee_serve.py') sieve $(pgrep -fc '[g]bsd.py --seed') ready $(ls /dev/shm/ready/c*/*.manifest.json 2>/dev/null | wc -l) fallback $(cat fallback_c*.log 2>/dev/null | wc -l)"
echo "relaunches in window: $(find . -maxdepth 1 -name '*.launch.log' -mmin -$((H*60)) -exec grep -c 'WATCHDOG RELAUNCH' {} + 2>/dev/null | awk -F: '{s+=$2} END{print s+0}') | daemon resumes: $(grep -c 'resuming seed' gbsd_sieve.log 2>/dev/null) | root free $(df -h / | awk 'NR==2{print $4}') shm free $(df -h /dev/shm | awk 'NR==2{print $4}')"
grep -h "LADDER ERROR\|FAIL" hunt_s1*.log 2>/dev/null | grep -v "FOSSIL COPY" | tail -2 | cut -c1-120
