#!/bin/bash
# gate_856.sh -- v8.56 (single-class) gates ON THE BOX, beside production: the CPU gates of gate_856_cpu.py plus the GPU part on one
# sieve card for a few minutes (depth 1e8, ~150 MB of card memory). Nothing in production is touched: test seeds 73xx, own --state /
# --out under $W, builds under $W. Production cache (.sc_cache) and predictor tables (/dev/shm/pred_*) are read (missing tables built atomically).
# usage: bash gate_856.sh NEWKIT [CARD]     NEWKIT = the extracted v8.56 kit dir; the v8.55 kit = $K. CARD = a sieve card (default 7).
# PASS = every gate PASS; the receipt $W/gate_856_receipt.json (with the gated sources' hashes) is what deploy_856.sh demands.
set -u; R=/root/beacon/raid610; K=/root/beacon/p3/o1_kit; PY=/venv/main/bin/python3; NEW=${1:?usage: gate_856.sh NEWKIT [CARD]}; CARD=${2:-7}
NEW=$(cd "$NEW" && pwd); W=/root/beacon/m357/gate856; rm -rf $W; mkdir -p $W/gpu_old $W/gpu_new
grep -q -- "--kclass" $NEW/gbsd.py || { echo "NEWKIT $NEW is not v8.56 (gbsd.py has no --kclass)"; exit 2; }
grep -q -- "--kclass" $K/gbsd.py && { echo "$K is already v8.56 - the v8.55 reference kit is gone (use the kit backup: K=/root/beacon/p3/o1_kit_v855)"; exit 2; }
CC=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d .)
for v in old new; do src=$K; [ $v = new ] && src=$NEW
  /usr/local/cuda/bin/nvcc -O3 -shared -Xcompiler -fPIC -gencode arch=compute_$CC,code=sm_$CC -o $W/gpu_$v/gbs.so $src/gbs.cu || { echo "G-856-B1 build ($v): FAIL"; exit 2; }
done
echo "G-856-B1 build: PASS (gbs.cu old $(sha256sum $K/gbs.cu | cut -c1-12) new $(sha256sum $NEW/gbs.cu | cut -c1-12), sm_$CC) | card $CARD for ~5 min"
nice -n 5 $PY $NEW/gate_856_cpu.py --old $K --new $NEW --work $W --cache $R/.sc_cache --threads 16 --workers 8 --sample 400 \
  --gpu --card $CARD --old-gpu-so $W/gpu_old/gbs.so --new-gpu-so $W/gpu_new/gbs.so --ref-all 2>&1 | grep -v "^$" | tee $W/gate_856_run.log
grep -q "^GATE 856: PASS" $W/gate_856_run.log && { echo "$(date -u +%FT%TZ) gate_856 PASS ($(grep -c ': PASS ' $W/gate_856_run.log) gates) new kit $NEW" >> $R/shadow_receipts.txt; echo "GATES DONE: PASS -> bash $NEW/deploy_856.sh $NEW"; exit 0; }
echo "GATES DONE: FAIL - nothing deployed; send $W/gate_856_run.log"; exit 2
