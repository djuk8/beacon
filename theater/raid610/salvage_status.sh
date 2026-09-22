#!/bin/bash
# salvage_status.sh -- one-screen health of the salvage pipeline: production, backlog, sweeper, harvest.
# Read-only. Alarms are plain lines starting with ALARM:. v1.1: find-based counts (ls glob overflowed at 4k files -> false zero). (C, 2026-08-25)
R=${R:-$HOME/beacon/raid610}; cd "$R" || exit 1
now=$(date -u +%s)
echo "==== salvage pipeline $(date -u +%FT%TZ) ===="
# --- 1. fossil production (the loop side): creation rate proves rungs are climbing
for ring in 6 7 8; do
  tot=$(find hunt_s* -name "sc_r0${ring}_*.manifest.json" 2>/dev/null | wc -l)
  new2=$(find hunt_s* -name "sc_r0${ring}_*.manifest.json" -mmin -120 2>/dev/null | wc -l)
  echo "r${ring}: backlog ${tot} unswept | created last 2h: ${new2}"
done
r8=$(find hunt_s* -name "sc_r08_*.manifest.json" 2>/dev/null | wc -l)
[ "$r8" = 0 ] && echo "note: r8 = 0 -> rung-8 not producing yet (loop v2.5 + ~3/day expected once live)"
# --- 2. sweeper liveness
if pgrep -f "salvage_v0.py" >/dev/null; then echo "sweeper: RUNNING (pid $(pgrep -f salvage_v0.py | head -1))"
elif [ -f .salvage.lock ]; then p=$(cat .salvage.lock); kill -0 "$p" 2>/dev/null && echo "sweeper: lock held live pid $p" || echo "ALARM: stale .salvage.lock (dead pid $p) -- rm .salvage.lock"
else echo "sweeper: idle (no lock)"; fi
# --- 3. harvest (the ledger): rate, staleness, gems
if [ -f salvage_finds.log ]; then
  tot=$(wc -l < salvage_finds.log)
  age=$(( (now - $(stat -c %Y salvage_finds.log)) / 60 ))
  ts24=$(grep -c "$(date -u +%Y-%m-%d)T" salvage_finds.log 2>/dev/null)
  echo "ledger: ${tot} walks total | last write ${age} min ago | timestamped-today: ${ts24}"
  echo "  top today:"; grep "$(date -u +%Y-%m-%d)T" salvage_finds.log 2>/dev/null | sort -k2 -rn | head -3 | sed 's/^/    /'
  echo "  top last-2000 (any era):"; tail -2000 salvage_finds.log | sort -k2 -rn | head -3 | sed 's/^/    /'
  backlog=$(find hunt_s* -name "sc_r06_*.manifest.json" 2>/dev/null | wc -l)
  [ "$age" -gt 240 ] && [ "$backlog" -gt 50 ] && echo "ALARM: ledger silent ${age} min with r6 backlog ${backlog} -- sweeper stalled?"
else echo "ALARM: no salvage_finds.log in $R"; fi
# --- 4. last sweep run log (debuggability)
L=$(ls -t salvage_r*_*.log 2>/dev/null | head -1)
[ -n "$L" ] && { echo "last sweep log: $L"; grep -c "GAP" "$L" | sed 's/^/  walks logged: /'; grep -m2 -i "error\|Traceback" "$L" | sed 's/^/  ALARM in log: /'; tail -2 "$L" | sed 's/^/  /'; }
