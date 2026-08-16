#!/bin/bash
set -u
cd ~/beacon/mono/hunt_s1
CMN="--zd 61493 --merit 20.05 --swap 2 3 5 7 11 13 --deep-q 1000000000 --seed 1 --rings 251254,388962,500622,614004"
for BID in 0001 0002 0003; do
  for R in 1 2 3 4; do
    B=sc_r0${R}_${BID}.bin
    [ -f "$B" ] || continue
    if [ ! -f "${B%.bin}.v.bin" ]; then
      python3 ../pfgw_drv.py "$B" "${B%.bin}.v.bin" -j 56 || exit 2
    fi
    python3 ../scanhunt_v0.py fold --round $R --bin "$B" $CMN || exit 2
    [ $R -lt 4 ] && python3 ../scanhunt_v0.py make --round $((R+1)) $CMN
  done
  if [ -s sc_carry_r04.json ] && python3 -c "import json,sys;sys.exit(0 if json.load(open('sc_carry_r04.json'))['ks'] else 1)"; then
    cp sc_carry_r04.json FINALIST_${BID}.json
    echo "FINALIST block $BID -- STOP before finish (gmpy2 interior trap)"; exit 3
  fi
done
cd ~/beacon/mono
exec ./hunt_loop.sh 1 0
