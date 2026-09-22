#!/bin/bash
# box_status.sh -- all cards: shadow_status per card + box totals (rung-1 w/s, tests/s). Read-only.
M=${M:-20}; R=$HOME/beacon/raid610; tw=0; tt=0
for c in 0 1 2 3; do [ -f $R/queue/c$c/ledger.jsonl ] || continue; echo "=== card $c ==="; C=$c M=$M bash ~/beacon/p3/o1_kit/shadow_status.sh | grep -E "rung-1|loops alive|since latest"; done
echo "box: venue $(cat $R/VENUE.txt 2>/dev/null || echo raid610) loops $(pgrep -fc raid_loop_v2.sh) feeders $(pgrep -fc "^/venv/main/bin/python3 /root/beacon/p3/ee_serve.py") Q=$(cat $R/Q.txt 2>/dev/null) LPC=$(cat $R/LPC.txt 2>/dev/null)+$(cat $R/EXTRA.txt 2>/dev/null) KWIN=$(cat $R/KWIN.txt 2>/dev/null) disk $(df -h / | awk 'NR==2{print $4" free"}') shm $(df -h /dev/shm | awk 'NR==2{print $3"/"$2}')"
python3 - "$R" "$M" <<'PY'
import sys, json, time, glob
R, m = sys.argv[1], float(sys.argv[2]); t0 = time.time() - m*60; ks = te = 0; first = None
for p in glob.glob(f"{R}/queue/c*/ledger.jsonl"):
    for l in open(p):
        d = json.loads(l)
        if d["ts"] < t0: continue
        first = min(first or d["ts"], d["ts"]); te += d["tested"]; ks += d["ks"] if int(d["round"]) == 1 else 0
span = max(1, time.time() - (first or time.time()))
print(f"BOX last {m:.0f} min: rung-1 windows/s {ks/span:,.0f}   tests/s {te/span:,.0f}   (R1 reference 14,500 w/s)")
PY

# feed health (sieve daemons vs fallback makes), v8.19
for c in 0 1 2 3; do printf "feed c$c: daemons %s ready %s fallback-makes(last 60min) %s\n" "$(pgrep -fc "bsd.py --seed [0-9]* --card $c ")" "$(ls /root/beacon/raid610/ready/c$c/*.manifest.json 2>/dev/null | wc -l)" "$(find /root/beacon/raid610 -maxdepth 1 -name fallback_c$c.log -mmin -60 -exec wc -l {} \; 2>/dev/null | awk '{print $1}' | head -1)"; done

echo "disk: root $(df -h / | awk 'NR==2{print $4" free ("$5" used)"}')  shm $(df -h /dev/shm | awk 'NR==2{print $4" free"}')"
