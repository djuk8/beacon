#!/bin/bash
# go_crown.sh -- migrate box1 from raid610 to the CROWN venue in one supervised pass. (C, 2026-08-23)
# tree-kill stop (receipt) -> venue files -> install kit -> G-L2 mint gate on ONE block (abort on fail)
# -> watchdog crontab -> onstart (16 feeders, 360 crown loops, seeds 1101-1460) -> receipt.
set -uo pipefail
R=$HOME/beacon/raid610; P3=$HOME/beacon/p3; PY=/venv/main/bin/python3; K=$P3/o1_kit
cd "$R" || exit 1
crontab -l > "$P3/crontab_saved_$(date -u +%s).txt" 2>/dev/null; crontab -r 2>/dev/null   # DISARM for the whole migration (watchdog-contamination lesson, 2026-08-26)
pkill -f sampler.sh; pkill -f ladder.py; pkill -f bsd.py; pkill -f gbsd.py; pkill -f raid_loop_v2.sh; rm -rf /dev/shm/ready ~/beacon/raid610/ready; mkdir -p /dev/shm/ready && ln -sfn /dev/shm/ready ~/beacon/raid610/ready   # ready queues on tmpfs: claims are renames, never disk copies (v8.26; the overlay filled at 64 rings/card); pkill -TERM -f ee_serve.py; sleep 3
pkill -9 -f 'scanhunt_v0.py make'; pkill -9 -f 'scanhunt_v0.py fold'; pkill -9 -f ee_serve.py 2>/dev/null; pkill -9 -f g1_fermat 2>/dev/null
# second sweep: stragglers observed surviving one pass
sleep 2; pkill -9 -f scanhunt_v0.py 2>/dev/null
sleep 5; rm -rf /dev/shm/beacon/*
echo "$(date -u +%FT%TZ) RAID610 STOP (venue migration): procs left $(pgrep -fc 'raid_loop|ee_serve|scanhunt|g1_fermat' || echo 0)" | tee -a shadow_receipts.txt
# EXTRA 85 -> 700 loops: deep cycle ~159s x 4.4 rings/s (measured 21 s/make on quiet box)
echo crown > VENUE.txt; echo 1000000 > Q.txt; echo 90 > LPC.txt; echo ${EXTRA:-85} > EXTRA.txt
echo ${KWIN:-250000} > KWIN.txt
echo ${DEEPQ:-100000000} > DEEPQ.txt; echo ${SELECT:-12} > SELECT.txt; echo ${DEEPR:-1} > DEEPR.txt; echo ${BSD:-3} > BSD.txt; echo ${BSDQ:-10000000000} > BSDQ.txt; echo ${BSDT:-4} > BSDT.txt; echo ${BSDN:-auto} > BSDN.txt; echo ${BSDS:-2} > BSDS.txt; echo ${BSDNICE:-5} > BSDNICE.txt; echo ${BSDPB:-100000} > BSDPB.txt; echo ${BSDALPHA:-0.6} > BSDALPHA.txt; echo ${TMAXHI:-1.5} > TMAXHI.txt; echo ${SIEVECARD:-3} > SIEVECARD.txt; echo ${SIEVETEST:-1} > SIEVETEST.txt; echo ${LADDER:-1} > LADDER.txt; echo ${LWORKERS:-12} > LWORKERS.txt; echo ${LMAXR1:-100} > LMAXR1.txt; echo ${GPUCORES:-0-31} > GPUCORES.txt; echo ${HERDCORES:-32-255} > HERDCORES.txt; echo ${MAKESLOTS:-64} > MAKESLOTS.txt; echo ${CHUNK:-6} > CHUNK.txt; echo ${GROWTH:-1.15} > GROWTH.txt
cp "$K/venue.py" "$R/" 2>/dev/null; read VZD VD VBITS VKDIG VMERIT VLAD <<< "$(cd "$R" && PYTHONPATH="$R:$K" $PY -c "import venue; v=venue.load(); print(v['zd'], v['d'], v['bits'], v['kdig'], v['merit'], v['ladder'])")"; VSWAP=$(cd "$R" && PYTHONPATH="$R:$K" $PY -c "import venue; print(' '.join(map(str, venue.load()['swap'])))")
[ -s "$VLAD" ] || cp "$K/$VLAD" . 2>/dev/null; [ -s "$VLAD" ] || { echo "ladder design $VLAD missing: cd $R && PYTHONPATH=$R:$K $PY $K/ladder_crown.py edges"; exit 1; }
cp "$K/resonance_map.py" "$R/" 2>/dev/null; [ -f "$R/resonance_map.py" ] || { echo "resonance_map.py missing from the kit"; exit 1; }
PYTHONPATH="$R:$K" $PY "$K/prewarm_cache.py" || exit 1
cp "$K/raid_loop_v2.sh" "$R/raid_loop_v2.sh"; chmod +x "$R/raid_loop_v2.sh"; cp "$K/ladder.py" "$R/ladder.py"
cp "$K/scanhunt_v0.py" "$K/fastmake.py" "$K/deep_primes.py" "$R/" && ( cd "$R" && gcc -O3 -shared -fPIC -o fastmake_c.so "$K/fastmake_c.c" ) || { echo "deep install failed"; exit 1; }
cp $K/bsd.py $K/gbsd.py $K/bs_api.c $K/bsieve.c $K/gbs.cu ~/beacon/raid610/ && (cd ~/beacon/raid610 && gcc -O3 -march=native -shared -fPIC -o bs_api.so bs_api.c -lpthread && ([ -f gbs.so ] && [ gbs.so -nt gbs.cu ] || /usr/local/cuda/bin/nvcc -O3 -shared -Xcompiler -fPIC -gencode arch=compute_120,code=sm_120 -o gbs.so gbs.cu)) || { echo "bs_api.so build FAILED"; exit 1; }
echo "deep stack: scanhunt $(sha256sum $R/scanhunt_v0.py | cut -c1-12) fastmake $(sha256sum $R/fastmake.py | cut -c1-12) c.so $(sha256sum $R/fastmake_c.so | cut -c1-12)"
cp "$K/ee_serve.py" "$P3/ee_serve.py"; cp "$K/onstart_raid_v2.sh" /root/onstart_raid_v2.sh; chmod +x /root/onstart_raid_v2.sh
echo "installed: loop $(sha256sum $R/raid_loop_v2.sh | cut -c1-12) onstart $(sha256sum /root/onstart_raid_v2.sh | cut -c1-12) feeder $(sha256sum $P3/ee_serve.py | cut -c1-12)"
W=$R/gate_crown; rm -rf "$W"; mkdir -p "$W"; cd "$W"
CR=$(cd "$R" && PYTHONPATH="$R:$K" $PY -c "import venue; print(venue.load()['rings'])")
$PY "$R/scanhunt_v0.py" make --round 1 --zd $VZD --swap $VSWAP --kdig $VKDIG --merit $VMERIT --Q 1000000 \
  --deep-q 0 --deep-from-ring 99 --rings $CR --bits $VBITS --seed 1101 --kblock 20000 > make.log 2>&1 || { echo "G-L2: mint failed: $(tail -2 make.log)"; exit 1; }
B=$(ls sc_r01_[0-9]*.bin | head -1)
( cd "$R" && PYTHONPATH="$R" $PY "$K/ladder_crown.py" gate "$W/${B%.bin}" ) | tee "$W/gate.log"
grep -q "PASS" "$W/gate.log" || { echo "G-L2: FAIL -- venue NOT launched"; exit 1; }
rm -f "$W/$B" 2>/dev/null
echo "$(date -u +%FT%TZ) G-L2 PASS ($B)" | tee -a "$R/shadow_receipts.txt"
cd "$R"; B2=$(ls -t $P3/crontab_backup_*.txt 2>/dev/null | head -1); if [ -n "$B2" ]; then sed "s|onstart_raid.sh|onstart_raid_v2.sh|g" "$B2" > /tmp/cron_v2.txt; else printf "@reboot /root/onstart_raid_v2.sh\n*/10 * * * * /root/onstart_raid_v2.sh\n" > /tmp/cron_v2.txt; fi; grep -q "queue/c\*/done" /tmp/cron_v2.txt || echo '23 * * * * find /root/beacon/raid610/queue/c*/done -name "*.json" -mmin +60 -delete' >> /tmp/cron_v2.txt
grep -q 'sc_r0\[678\]' /tmp/cron_v2.txt || echo '17 * * * * find /root/beacon/raid610/hunt_s1* -name "sc_r0[678]_*.bin" -mmin +5 -delete' >> /tmp/cron_v2.txt
grep -q "harvest_hourly.sh" /tmp/cron_v2.txt || echo "17 * * * * /root/beacon/p3/o1_kit/harvest_hourly.sh >> /root/beacon/raid610/harvest.log 2>&1" >> /tmp/cron_v2.txt   # hourly fossil harvest (the old sweeper died 2026-08-25 unnoticed for 24 days)
crontab /tmp/cron_v2.txt
NC=$(nvidia-smi -L 2>/dev/null | wc -l); [ "$NC" -ge 1 ] || NC=4; for c in $(seq 0 $((NC-1))); do mkdir -p queue/c$c; for s in $(seq $((1101+c*90)) $((1190+c*90))); do f=hunt_s$s.log; [ -f $f ] && echo "$s $(stat -c%s $f)" || echo "$s 0"; done >> queue/c$c/log_offsets.txt; done
rm -f queue/c*/req/*.json queue/c*/claimed/*.json 2>/dev/null
VENUE=crown /root/onstart_raid_v2.sh; sleep 30
echo "$(date -u +%FT%TZ) CROWN START: feeders $(pgrep -fc ee_serve.py) loops $(pgrep -fc raid_loop_v2.sh) rings $CR cap 45.0" | tee -a shadow_receipts.txt
