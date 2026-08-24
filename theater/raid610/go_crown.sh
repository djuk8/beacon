#!/bin/bash
# go_crown.sh -- migrate box1 from raid610 to the CROWN venue in one supervised pass. (C, 2026-08-23)
# tree-kill stop (receipt) -> venue files -> install kit -> G-L2 mint gate on ONE block (abort on fail)
# -> watchdog crontab -> onstart (16 feeders, 360 crown loops, seeds 1101-1460) -> receipt.
set -uo pipefail
R=$HOME/beacon/raid610; P3=$HOME/beacon/p3; PY=/venv/main/bin/python3; K=$P3/o1_kit
cd "$R" || exit 1
pkill -f raid_loop_v2.sh; pkill -TERM -f ee_serve.py; sleep 3
pkill -9 -f 'scanhunt_v0.py make'; pkill -9 -f 'scanhunt_v0.py fold'; pkill -9 -f ee_serve.py 2>/dev/null; pkill -9 -f g1_fermat 2>/dev/null
sleep 5; rm -rf /dev/shm/beacon/*
echo "$(date -u +%FT%TZ) RAID610 STOP (venue migration): procs left $(pgrep -fc 'raid_loop|ee_serve|scanhunt|g1_fermat' || echo 0)" | tee -a shadow_receipts.txt
echo crown > VENUE.txt; echo 1000000 > Q.txt; echo 90 > LPC.txt; echo 0 > EXTRA.txt; echo 250000 > KWIN.txt
[ -s ladder_crown.json ] || { echo "ladder_crown.json missing -- run G-L1 first"; exit 1; }
$PY "$K/prewarm_cache.py" || exit 1
cp "$K/raid_loop_v2.sh" "$R/raid_loop_v2.sh"; chmod +x "$R/raid_loop_v2.sh"
cp "$K/ee_serve.py" "$P3/ee_serve.py"; cp "$K/onstart_raid_v2.sh" /root/onstart_raid_v2.sh; chmod +x /root/onstart_raid_v2.sh
echo "installed: loop $(sha256sum $R/raid_loop_v2.sh | cut -c1-12) onstart $(sha256sum /root/onstart_raid_v2.sh | cut -c1-12) feeder $(sha256sum $P3/ee_serve.py | cut -c1-12)"
W=$R/gate_crown; rm -rf "$W"; mkdir -p "$W"; cd "$W"
CR=1568,4374,7244,10198,13500,17734,22818,31576
$PY "$R/scanhunt_v0.py" make --round 1 --zd 1439 --swap 2 3 5 7 11 --kdig 13 --merit 45.0 --Q 1000000 \
  --deep-q 0 --deep-from-ring 99 --rings $CR --bits 2048 --seed 1101 --kblock 20000 > make.log 2>&1 || { echo "G-L2: mint failed: $(tail -2 make.log)"; exit 1; }
B=$(ls sc_r01_[0-9]*.bin | head -1)
( cd "$R" && PYTHONPATH="$R" $PY "$K/ladder_crown.py" gate "$W/${B%.bin}" ) | tee "$W/gate.log"
grep -q "PASS" "$W/gate.log" || { echo "G-L2: FAIL -- venue NOT launched"; exit 1; }
rm -f "$W/$B" 2>/dev/null
echo "$(date -u +%FT%TZ) G-L2 PASS ($B)" | tee -a "$R/shadow_receipts.txt"
cd "$R"; B2=$(ls -t $P3/crontab_backup_*.txt | head -1); sed "s|onstart_raid.sh|onstart_raid_v2.sh|g" "$B2" > /tmp/cron_v2.txt; crontab /tmp/cron_v2.txt
for c in 0 1 2 3; do mkdir -p queue/c$c; for s in $(seq $((1101+c*90)) $((1190+c*90))); do f=hunt_s$s.log; [ -f $f ] && echo "$s $(stat -c%s $f)" || echo "$s 0"; done >> queue/c$c/log_offsets.txt; done
rm -f queue/c*/req/*.json queue/c*/claimed/*.json 2>/dev/null
VENUE=crown /root/onstart_raid_v2.sh; sleep 30
echo "$(date -u +%FT%TZ) CROWN START: feeders $(pgrep -fc ee_serve.py) loops $(pgrep -fc raid_loop_v2.sh) rings $CR cap 45.0" | tee -a shadow_receipts.txt
