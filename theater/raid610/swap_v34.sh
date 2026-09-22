#!/bin/bash
# swap_v34.sh -- upgrade box1's driver to v3.4 (base-2 ladder + O4' schedule) under full gates. (C, 2026-08-24)
# Sequence: tree-kill stop (receipt) -> build v3.4 (sm_120) -> gate_r4 R0-R3+R2b -> gate_serve S1,S6
# -> install binary + feeder -> relaunch crown -> receipt. ABORTS before install on any gate FAIL.
set -uo pipefail
R=$HOME/beacon/raid610; P3=$HOME/beacon/p3; K=$P3/o1_kit; PY=/venv/main/bin/python3
cd "$R" || exit 1
crontab -l > "$P3/crontab_live_$(date -u +%s).txt" 2>/dev/null; crontab -r 2>/dev/null   # disarm the watchdog for the whole gate window (Text-file-busy incident 2026-08-24)
pkill -f raid_loop_v2.sh; pkill -TERM -f ee_serve.py; sleep 3
pkill -9 -f 'scanhunt_v0.py make'; pkill -9 -f 'scanhunt_v0.py fold'; pkill -9 -f ee_serve.py 2>/dev/null; pkill -9 -f g1_fermat 2>/dev/null
sleep 5
echo "$(date -u +%FT%TZ) CROWN STOP (v3.4 swap): procs left $(pgrep -fc 'raid_loop|ee_serve|scanhunt|g1_fermat' || echo 0)" | tee -a shadow_receipts.txt
# --- restore certified v3.3 as the production binary FIRST (the 2026-08-24 R0 incident overwrote it)
NVCC=$(command -v nvcc || ls /usr/local/cuda/bin/nvcc 2>/dev/null | head -1)
[ "$(sha256sum "$K/g1_fermat_v33.cu" | cut -c1-12)" = f1b64d4fd752 ] || { echo "v3.3 source hash mismatch -- ABORT"; exit 1; }
cp "$K/g1_fermat_v33.cu" "$P3/g1_fermat_v3.cu"
( cd "$P3" && $NVCC -O3 -gencode arch=compute_120,code=sm_120 -I../CGBN/include g1_fermat_v3.cu -o g1_fermat_v3 -lgmp ) > "$P3/rebuild_v33.log" 2>&1 || { echo "v3.3 rebuild failed: $(grep -m2 error "$P3/rebuild_v33.log")"; exit 1; }
echo "$(date -u +%FT%TZ) PRODUCTION RESTORED to v3.3: bin $(sha256sum "$P3/g1_fermat_v3" | cut -c1-12) src f1b64d4fd752" | tee -a shadow_receipts.txt
echo "$(date -u +%FT%TZ) LEDGER QUARANTINE for E-stats: 2026-08-24T12:10Z .. this restore (ungated v3.4 era; finds re-proof as always)" | tee -a shadow_receipts.txt
# mint two fresh crown-venue fixtures for R1/R2 (production make, gate seeds; ~250 MB each)
FX=$P3/gate_fx_v34; rm -rf "$FX"; mkdir -p "$FX/f1" "$FX/f2"
CR=1568,4374,7244,10198,13500,17734,22818,31576
for i in 1 2; do ( cd "$FX/f$i" && $PY "$R/scanhunt_v0.py" make --round 1 --zd 1439 --swap 2 3 5 7 11 \
  --kdig 13 --merit 45.0 --Q 1000000 --deep-q 0 --deep-from-ring 99 --rings $CR --bits 2048 \
  --seed $((9300+i)) --kblock 20000 > make.log 2>&1 ) || { echo "fixture mint $i failed: $(tail -2 $FX/f$i/make.log)"; exit 1; }; done
F1=$(ls "$FX"/f1/sc_r01_[0-9]*.bin | head -1); F2=$(ls "$FX"/f2/sc_r01_[0-9]*.bin | head -1)
[ -s "$F1" ] && [ -s "$F2" ] || { echo "fixtures missing"; exit 1; }
echo "fixtures: $F1 $F2"
cd "$K"
FIXTURES="$F1 $F2" GENCODE="-gencode arch=compute_120,code=sm_120" V3=$P3/g1_fermat_v34 bash gate_r4.sh 2>&1 | tee $P3/gate_r4_v34.log | grep -E '^R[0-9]|IDENTICAL|PASS|FAIL|t/s'
grep -q "ALL PASS" $P3/gate_r4_v34.log || { echo "gate_r4 v3.4: FAIL -- NOT installed; relaunch old stack with: bash $K/go_crown.sh"; exit 1; }
DRV=$P3/g1_fermat_v2 DRV_EE=$P3/g1_fermat_v34 BITS=2048 GPU=0 bash gate_serve.sh 2>&1 | tee $P3/gate_serve_v34.log | grep -E '^S[0-9]|PASS|FAIL'
grep -q "ALL PASS" $P3/gate_serve_v34.log || { echo "gate_serve v3.4: FAIL -- NOT installed"; exit 1; }
cp $P3/g1_fermat_v34 $P3/g1_fermat_v3 || { echo "install cp FAILED"; exit 1; }
[ "$(sha256sum $P3/g1_fermat_v3 | cut -c1-12)" = "$(sha256sum $P3/g1_fermat_v34 | cut -c1-12)" ] || { echo "install SHA MISMATCH"; exit 1; }
cp "$K/ee_serve.py" $P3/ee_serve.py
echo "installed: v3 $(sha256sum $P3/g1_fermat_v3 | cut -c1-12) (v3.4) feeder $(sha256sum $P3/ee_serve.py | cut -c1-12) schedule chunk6/growth1.15"
echo "$(date -u +%FT%TZ) V34 GATES PASS + INSTALLED" | tee -a "$R/shadow_receipts.txt"
cd "$R"; VENUE=crown /root/onstart_raid_v2.sh; sleep 30
echo "$(date -u +%FT%TZ) CROWN RESTART on v3.4: feeders $(pgrep -fc ee_serve.py) loops $(pgrep -fc raid_loop_v2.sh)" | tee -a shadow_receipts.txt
