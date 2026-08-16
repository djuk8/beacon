#!/bin/bash
# hunt_loop.sh v3 -- pipelined block cycler, one instance per card.
#   ./hunt_loop.sh <SEED> <GPU_ID> [N_BLOCKS]
set -u
S=$1; G=$2; N=${3:-100000}
RINGS=42422,89574,135714,187576,213166
KB=3000
DQ=1000000000
BASE=~/beacon/arch6150
mkdir -p $BASE/hunt_s$S && cd $BASE/hunt_s$S || exit 1
sleep $(( (S-1)*420 ))   # stagger seeds so round-1 disk writes never stack
CMN="--zd 14341 --merit 30.10 --swap 2 3 5 7 11 13 --deep-q $DQ --seed $S --rings $RINGS"
PFPID=""
for ((b=1;b<=N;b++)); do
  echo "=== seed $S block $b $(date +%H:%M:%S) ==="
  if [ -n "$PFPID" ]; then
    wait $PFPID; PFPID=""          # prefetched round-1 make from last block
  fi
  if [ -z "$(ls sc_r01_*[0-9].bin 2>/dev/null)" ]; then
    env PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
      python3 $BASE/scanhunt_v0.py make --round 1 --kblock $KB $CMN || exit 2
  fi
  # PREFETCH: next block's round-1 make overlaps this block's GPU drives
  ( env PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
      python3 $BASE/scanhunt_v0.py make --round 1 --kblock $KB $CMN \
      > .prefetch_b$((b+1)).log 2>&1 ) &
  PFPID=$!
  for r in 1 2 3 4 5; do
    B=$(ls sc_r0${r}_*[0-9].bin 2>/dev/null | sort | head -1)
    [ -z "$B" ] && break
    ok=0
    for try in 1 2 3; do
      rm -f "${B%.bin}.v.bin"
      CUDA_VISIBLE_DEVICES=$G $BASE/../p3/g1_fermat "$B" "${B%.bin}.v.bin" && { ok=1; break; }
      echo "driver failed (try $try) on $B -- retrying in 30s"; sleep 30
    done
    [ $ok -eq 1 ] || exit 3
    env PYTHONUNBUFFERED=1 python3 $BASE/scanhunt_v0.py fold --round $r --bin "$B" $CMN || exit 4
    rm -f "$B" "${B%.bin}.v.bin"
    if [ $r -lt 5 ]; then
      env PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 \
        python3 $BASE/scanhunt_v0.py make --round $((r+1)) --kblock $KB $CMN
    fi
  done
  env PYTHONUNBUFFERED=1 python3 $BASE/scanhunt_v0.py finish $CMN \
    --max-prp 60000 2>&1 | tee -a finds.log
done
