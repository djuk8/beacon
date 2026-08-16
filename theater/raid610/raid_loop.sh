#!/bin/bash
S=$1; C=$2
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
RINGS=1568,4374,7244,10198,13500,17734,26542
ARGS="--zd 1439 --swap 2 3 5 7 11 --kdig 13 --merit 37.8241 --Q 100000 \
 --deep-q 0 --deep-from-ring 99 --rings $RINGS --bits 2048 --seed $S --kblock 20000"
mkdir -p hunt_s$S && cd hunt_s$S
while true; do
  python3 ../scanhunt_v0.py make --round 1 $ARGS || exit 1
  B=$(ls -t sc_r01_*.bin | head -1)
  for R in 1 2 3 4 5 6 7; do
    BB=${B/r01/r0$R}
    [ -f "$BB" ] || break
    ok=0
    for try in 1 2 3; do
      CUDA_VISIBLE_DEVICES=$C flock /tmp/raidgpu$C.lock \
        ~/beacon/p3/g1_fermat_v2 $BB ${BB%.bin}.v.bin \
        && [ -s "${BB%.bin}.v.bin" ] && { ok=1; break; }
      echo "DRIVE RETRY $try $BB"; sleep $((try*5))
    done
    [ $ok = 1 ] || { echo "DRIVE FAIL $BB -- block abandoned"; \
      rm -f "$BB" "${BB%.bin}.v.bin"; break; }
    python3 ../scanhunt_v0.py fold --round $R --bin $BB $ARGS \
      || { echo "FOLD FAIL $BB -- block abandoned"; break; }
    rm -f "$BB" "${BB%.bin}.v.bin"
    if [ $R -le 5 ]; then rm -f "${BB%.bin}.manifest.json"; fi
    [ $R -lt 7 ] && python3 ../scanhunt_v0.py make --round $((R+1)) $ARGS
  done
  python3 ../scanhunt_v0.py finish $ARGS >> finish.log 2>&1
done
