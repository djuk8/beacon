#!/bin/bash
# go_fourwide.sh -- from a one-card shadow to the full box under kit v3.5: stop shadow loops+feeders (receipt),
# write the box Q setting, install the kit loop, restore the watchdog crontab, run onstart (feeders then 121 loops). (C, 2026-08-22)
set -uo pipefail
R=$HOME/beacon/raid610; P3=$HOME/beacon/p3; BOXQ=${BOXQ:-1000000}; LPC=${LPC:-90}; EXTRA=${EXTRA:-0}; KWIN=${KWIN:-250000}   # Q=1e7 struck 2026-08-23: memory-bandwidth wall at concurrency (MACHINERY 8.13); deep Q lives in O3
cd "$R" || exit 1
pkill -f raid_loop_v2.sh; sleep 5; pkill -TERM -f ee_serve.py; for i in $(seq 120); do pgrep -f ee_serve.py >/dev/null || break; sleep 1; done; pkill -9 -f ee_serve.py 2>/dev/null
echo "$(date -u +%FT%TZ) SHADOW STOP: loops $(pgrep -fc raid_loop_v2.sh) feeders $(pgrep -fc ee_serve.py) ledger $(wc -l < queue/c0/ledger.jsonl)" | tee -a shadow_receipts.txt
echo "$BOXQ" > Q.txt; echo "$LPC" > LPC.txt; echo "$EXTRA" > EXTRA.txt; echo "$KWIN" > KWIN.txt; rm -f queue/c*/req/*.json queue/c*/claimed/*.json 2>/dev/null
mkdir -p "$R/.sc_cache" /dev/shm/beacon
/venv/main/bin/python3 "$P3/o1_kit/prewarm_cache.py" || { echo "cache pre-warm failed"; exit 1; }
cp "$P3/o1_kit/raid_loop_v2.sh" "$R/raid_loop_v2.sh"; cp "$P3/o1_kit/ee_serve.py" "$P3/ee_serve.py"; cp "$P3/o1_kit/onstart_raid_v2.sh" /root/onstart_raid_v2.sh; chmod +x "$R/raid_loop_v2.sh" /root/onstart_raid_v2.sh
echo "installed: loop $(sha256sum $R/raid_loop_v2.sh | cut -c1-12) feeder $(sha256sum $P3/ee_serve.py | cut -c1-12) v3 $(sha256sum $P3/g1_fermat_v3 | cut -c1-12) make $(sha256sum $R/scanhunt_v0.py | cut -c1-12) Q=$(cat Q.txt)"
B=$(ls -t $P3/crontab_backup_*.txt | head -1); sed "s|onstart_raid.sh|onstart_raid_v2.sh|g" "$B" > /tmp/cron_v2.txt; crontab /tmp/cron_v2.txt; echo "crontab (from $B, v2):"; crontab -l | grep -v '^#'
for c in 0 1 2 3; do mkdir -p queue/c$c; for s in $(seq $((101+c*LPC)) $((100+(c+1)*LPC))) $(seq $((702+c*EXTRA)) $((701+(c+1)*EXTRA))); do f=hunt_s$s.log; [ -f $f ] && echo "$s $(stat -c%s $f)" || echo "$s 0"; done >> queue/c$c/log_offsets.txt; done
LPC=$LPC EXTRA=$EXTRA KWIN=$KWIN /root/onstart_raid_v2.sh; sleep 30
echo "$(date -u +%FT%TZ) FOURWIDE START: feeders $(pgrep -fc ee_serve.py) loops $(pgrep -fc raid_loop_v2.sh) Q=$(cat Q.txt) LPC=$(cat LPC.txt)+$(cat EXTRA.txt) KWIN=$(cat KWIN.txt)" | tee -a shadow_receipts.txt
