#!/bin/bash
# resume_b1.sh -- finish block 1 from the banked round-1/2 state, one seed.
#   ./resume_b1.sh <SEED> <GPU_ID>       (run all four in parallel)
set -u
S=$1; G=$2
BASE=~/beacon/arch
CMN="--zd 6301 --swap 2 3 5 7 11 13 --deep-q 1000000000 --rings 14112,33622,54344,77524,100393"
cd $BASE/hunt_s$S || exit 1
for r in 2 3 4 5; do
  B=$(ls sc_r0${r}_*[0-9].bin 2>/dev/null | tail -1)
  if [ -n "$B" ]; then
    VB="${B%.bin}.v.bin"
    NEED=$(( ( $(stat -c%s "$B") - 16 ) / 2048 + 16 ))
    if [ ! -s "$VB" ] || [ "$(stat -c%s "$VB")" -ne "$NEED" ]; then
      rm -f "$VB"     # stale/partial verdicts are poison, not progress
      CUDA_VISIBLE_DEVICES=$G $BASE/../p3/g1_fermat "$B" "$VB" || \
        { sleep 30; rm -f "$VB"; CUDA_VISIBLE_DEVICES=$G $BASE/../p3/g1_fermat "$B" "$VB"; } || exit 3
    fi
  fi
  if [ -n "$B" ] && [ -s "${B%.bin}.v.bin" ] && [ ! -s "sc_carry_r0${r}.json" ]; then
    env PYTHONUNBUFFERED=1 python3 $BASE/scanhunt_v0.py fold --round $r $CMN || exit 4
    rm -f "$B" "${B%.bin}.v.bin"
  fi
  if [ $r -lt 5 ] && [ -s "sc_carry_r0${r}.json" ] && \
     [ -z "$(ls sc_r0$((r+1))_*[0-9].bin 2>/dev/null)" ]; then
    env PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 python3 $BASE/scanhunt_v0.py make \
      --round $((r+1)) $CMN
  fi
done
env PYTHONUNBUFFERED=1 python3 $BASE/scanhunt_v0.py finish $CMN --max-prp 60000 2>&1 | tee -a finds.log
echo "=== seed $S block 1 complete ==="
