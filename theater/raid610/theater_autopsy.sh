#!/bin/bash
# theater_autopsy.sh v1.0 -- READ-ONLY. Why is the stopped theater at 69 w/s?
set -uo pipefail
R=${R:-$HOME/beacon/raid610}; P3=${P3:-$HOME/beacon/p3}
hr(){ echo "------------------------------------------------------------------"; }
hr; echo "1. what the watchdog starts:"; for f in /root/onstart_raid.sh "$P3"/*.sh; do [ -f "$f" ] && { echo "== $f ($(wc -l < "$f") lines)"; grep -nE 'fastmake|scanhunt|raid_loop|--score|--deep|--Q|KB=|setsid|PYBIN|for |seq' "$f" | head -30; }; done
hr; echo "2. make/drive flags anywhere in the kit (the constants that must be grep-verified):"
grep -rnE -- '--score|--deep-q|--deep-from-ring|--Q [0-9]|KB *= *[0-9]+|span4e9|hook=' "$P3" "$HOME/beacon/deploy" "$HOME/beacon/kit"* 2>/dev/null | grep -v '\.log:' | cut -c1-160 | head -40
hr; echo "3. newest r01 manifest, its cfg block:"; m=$(find "$R" -name '*_r01_*.manifest.json' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2)
[ -n "$m" ] && python3 - "$m" <<'EOF'
import json,sys; d=json.load(open(sys.argv[1])); print(sys.argv[1]); print("keys:", list(d)); print("cfg:", json.dumps(d.get("cfg"), indent=None)[:800]); print("ks:", len(d.get("ks",[])), "sizes med:", sorted(d["sizes"])[len(d["sizes"])//2] if d.get("sizes") else None)
for k in ("t_make","make_s","t_trial_s","elapsed","started","finished","ts","seed","round"): 
    if k in d: print(k, "=", d[k])
EOF
hr; echo "4. ring interval per seed (time between consecutive r01 manifests in the same hunt dir), 6 busiest dirs:"
for d in $(find "$R" -maxdepth 1 -type d -name 'hunt_s*' | head -200); do n=$(ls "$d"/*_r01_*.manifest.json 2>/dev/null | wc -l); [ "$n" -ge 2 ] && echo "$n $d"; done | sort -rn | head -6 | while read n d; do
  echo "== $d ($n r01 manifests):"; ls -l --time-style=+%H:%M:%S "$d"/*_r01_*.manifest.json | awk '{print $6, $7}' | sort | tail -4 | sed 's/^/    /'; done
hr; echo "5. where do fossils go? dirs holding r01 manifests, with counts and age range:"
find "$HOME" -maxdepth 6 -name '*_r01_*.manifest.json' -printf '%h\n' 2>/dev/null | sort | uniq -c | sort -rn | head -8 | while read n d; do echo "  $n  $d  oldest $(ls -t "$d"/*_r01_*.manifest.json | tail -1 | xargs -I{} date -u -r {} +%m-%dT%H:%M)  newest $(ls -t "$d"/*_r01_*.manifest.json | head -1 | xargs -I{} date -u -r {} +%m-%dT%H:%M)"; done
hr; echo "6. loop logs: newest 3, with their first and last timestamped lines:"
find "$R" "$P3" -maxdepth 3 -name '*.log' -mmin -120 -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -3 | cut -d' ' -f2 | while read f; do echo "== $f ($(wc -l < "$f") lines)"; head -3 "$f" | cut -c1-150 | sed 's/^/    /'; echo "    ..."; grep -iE 'make|sieve|score|deep|took|elapsed|[0-9]+\.[0-9]+ ?s\b' "$f" | tail -6 | cut -c1-150 | sed 's/^/    /'; done
hr; echo "7. watchdog log format:"; [ -f /root/watchdog.log ] && { head -3 /root/watchdog.log; echo "..."; tail -3 /root/watchdog.log; echo "lines: $(wc -l < /root/watchdog.log), distinct: $(sort -u /root/watchdog.log | wc -l)"; }
hr; echo "8. CPU side during the soak (if sar/atop absent, just the loadavg now):"; cat /proc/loadavg; command -v sar >/dev/null && sar -q 1 1 | tail -2
