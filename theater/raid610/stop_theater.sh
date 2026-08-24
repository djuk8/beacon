#!/bin/bash
# stop_theater.sh v1.0 -- clean stop of the box1 raid theater (C, 2026-08-21).
# Order matters: watchdog cron OFF first (else it resurrects the loops within
# 10 min), then TERM the loops, then WAIT for in-flight driver launches to
# finish on their own (a killed driver leaves a half-written v.bin), then a
# receipt.  Nothing is deleted; crontab is backed up before editing.
#   bash stop_theater.sh            # read-only report, then asks YES
#   bash stop_theater.sh status     # report only
set -uo pipefail
P3=${P3:-$HOME/beacon/p3}; mkdir -p "$P3"; LOG=${LOG:-$P3/stop_theater.log}
PATTERN=${PATTERN:-raid_loop}; DRVPAT=${DRVPAT:-g1_fermat}; WD=${WD:-onstart}
say(){ echo "$@" | tee -a "$LOG"; }; stamp(){ date -u +'%FT%TZ'; }
report(){
  say "---- theater status $(stamp) host=$(hostname)"
  say "loops ($PATTERN): $(pgrep -fc "$PATTERN")   drivers ($DRVPAT): $(pgrep -fc "$DRVPAT")   ee_drive: $(pgrep -fc ee_drive)"
  say "crontab lines mentioning '$WD': $(crontab -l 2>/dev/null | grep -c "$WD")"; crontab -l 2>/dev/null | grep "$WD" | sed 's/^/    /' | tee -a "$LOG"
  command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader | sed 's/^/    gpu /' | tee -a "$LOG"
  say "newest manifests per rung (era marker):"
  for r in r01 r02 r03 r04 r05 r06 r07; do f=$(find "$HOME/beacon/raid610" -name "*_${r}_*.manifest.json" -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2); [ -n "$f" ] && say "    $r $(date -u -r "$f" +%FT%TZ) $(basename "$f")"; done
}
report
[ "${1:-}" = "status" ] && exit 0
read -r -p "STOP the theater now (watchdog off, loops TERM, drivers finish, receipt)?  type YES: " a; [ "$a" = "YES" ] || { say "aborted"; exit 1; }
T0=$(stamp); say "==== STOP requested $T0"
# 1. watchdog off, with backup
BK=$P3/crontab_backup_$(date -u +%Y%m%d_%H%M%S).txt
crontab -l > "$BK" 2>/dev/null && say "crontab backed up to $BK ($(wc -l < "$BK") lines)"
if grep -q "$WD" "$BK" 2>/dev/null; then
  grep -v "$WD" "$BK" | crontab - && say "watchdog lines removed from crontab (restore: crontab $BK)"
else say "no '$WD' lines in crontab (watchdog may live elsewhere -- check /etc/cron.d, systemd)"; fi
ls /etc/cron.d 2>/dev/null | grep -i -E "$WD|raid|watchdog" | sed 's|^|    /etc/cron.d/|' | tee -a "$LOG"
# 2. TERM the loops (parents), so no new launches are started
say "loops before: $(pgrep -fc "$PATTERN")"; pkill -TERM -f "$PATTERN"; sleep 3; say "loops after TERM: $(pgrep -fc "$PATTERN")"
# 3. let in-flight drivers finish (they write v.bin directly)
for i in $(seq 60); do n=$(pgrep -fc "$DRVPAT"); [ "$n" -eq 0 ] && break; [ $((i % 6)) -eq 0 ] && say "  waiting for $n in-flight driver launch(es) to finish ... ${i}0 s"; sleep 10; done
n=$(pgrep -fc "$DRVPAT"); [ "$n" -eq 0 ] && say "drivers drained cleanly" || say "WARN: $n driver(s) still running after 10 min -- leaving them; their rings are already fossils-in-waiting, do NOT kill -9"
# 4. anything of the loop family still alive?
left=$(pgrep -fc "$PATTERN"); if [ "$left" -gt 0 ]; then say "$left loop process(es) ignored TERM -> KILL"; pkill -KILL -f "$PATTERN"; sleep 2; fi
# 5. receipt
R=$P3/STOP_RECEIPT_$(date -u +%Y%m%d_%H%M%S).txt
{ echo "theater stop receipt"; echo "requested $T0 done $(stamp) host $(hostname) by $(id -un)"
  echo "loops now $(pgrep -fc "$PATTERN") drivers now $(pgrep -fc "$DRVPAT") crontab_backup $BK"
  echo "note: soak ended by decision (not by verdict); open item: theater rate read 249 w/s vs R1 14,500 (unresolved)"
} > "$R"; cat "$R" | tee -a "$LOG"
report
say "==== theater stopped. Treasury, finds dirs, manifests untouched. Restore watchdog: crontab $BK ; restart loops: /root/onstart_raid.sh"
