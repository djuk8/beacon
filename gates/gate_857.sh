#!/bin/bash
# gate_857.sh -- v8.57 (ring 2 deep-sieved on the GPU daemon) gates ON THE BOX, beside production: the CPU gates of gate_857_cpu.py
# plus the GPU part on one sieve card for a few minutes (depth 1e8, a few hundred MB of card memory). Nothing in production is touched:
# test seeds 78xx, own --state / --out under $W, builds under $W. Production cache and predictor tables are read.
# usage: bash gate_857.sh NEWKIT [CARD]     NEWKIT = the extracted v8.57 kit; the v8.56 kit = $K. CARD = a sieve card (default 7).
set -u; R=/root/beacon/raid610; K=/root/beacon/p3/o1_kit; PY=/venv/main/bin/python3; NEW=${1:?usage: gate_857.sh NEWKIT [CARD]}; CARD=${2:-7}
NEW=$(cd "$NEW" && pwd); W=/root/beacon/m357/gate857; rm -rf $W; mkdir -p $W/gpu_old $W/gpu_new
grep -q -- "--gpu-rings" $NEW/gbsd.py || { echo "NEWKIT $NEW is not v8.57 (gbsd.py has no --gpu-rings)"; exit 2; }
grep -q -- "--gpu-rings" $K/gbsd.py && { echo "$K is already v8.57 - the v8.56 reference kit is /root/beacon/p3/o1_kit_v856"; exit 2; }
grep -q -- "--kclass" $K/gbsd.py || { echo "$K is not v8.56 (run the v8.56 deploy first)"; exit 2; }
CC=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d .)
for v in old new; do src=$K; [ $v = new ] && src=$NEW
  /usr/local/cuda/bin/nvcc -O3 -shared -Xcompiler -fPIC -gencode arch=compute_$CC,code=sm_$CC -o $W/gpu_$v/gbs.so $src/gbs.cu || { echo "G-857-B1 build ($v): FAIL"; exit 2; }
done
echo "G-857-B1 build: PASS (gbs.cu old $(sha256sum $K/gbs.cu | cut -c1-12) new $(sha256sum $NEW/gbs.cu | cut -c1-12), sm_$CC) | card $CARD for ~5 min"
nice -n 5 $PY $NEW/gate_857_cpu.py --old $K --new $NEW --work $W --cache $R/.sc_cache --threads 16 --workers 8 --sample 400 \
  --gpu --card $CARD --old-gpu-so $W/gpu_old/gbs.so --new-gpu-so $W/gpu_new/gbs.so --ref-all 2>&1 | grep -v "^$" | tee $W/gate_857_run.log
grep -q "^GATE 857: PASS" $W/gate_857_run.log && { echo "$(date -u +%FT%TZ) gate_857 PASS ($(grep -c ': PASS ' $W/gate_857_run.log) gates) new kit $NEW" >> $R/shadow_receipts.txt; echo "GATES DONE: PASS -> bash $NEW/deploy_857.sh $NEW"; exit 0; }
echo "GATES DONE: FAIL - nothing deployed; send $W/gate_857_run.log"; exit 2
