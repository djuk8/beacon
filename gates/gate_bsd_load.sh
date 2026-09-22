#!/bin/bash
# gate_bsd_load.sh [Qd] [N per card] [threads] -- ring-to-ring of N*4 daemons at depth Qd running BESIDE production for ~6 rings each.
set -u; R=$HOME/beacon/raid610; K=$HOME/beacon/p3/o1_kit; PY=/venv/main/bin/python3; QD=${1:-1000000000}; N=${2:-2}; TH=${3:-4}; SH=${4:-2}; W=$HOME/beacon/m357/bsdload; rm -rf $W; mkdir -p $W
cp $K/scanhunt_v0.py $K/fastmake.py $K/bsd.py $K/bs_api.c $K/bsieve.c $R/ && (cd $R && gcc -O3 -shared -fPIC -o bs_api.so bs_api.c -lpthread) || { echo "build FAIL"; exit 2; }
for c in 0 1 2 3; do for d in $(seq 0 $((N-1))); do S=$((7301+c+10*d)); mkdir -p $W/c${c}_$d; ln -sfn $R/.sc_cache $W/c${c}_$d/.sc_cache
  ( cd $W/c${c}_$d && $PY $R/bsd.py --seed $S --card $c --out $W/c${c}_$d/ready --deepq $QD --select 12 --blocks 8 --threads $TH --shallow-threads $SH --ahead 100 --api $R/bs_api.so > log 2>&1 ) &
done; done
wait
echo "load bench: Qd=$QD, $((N*4)) daemons x ($TH sieve + $SH shallow) threads, nice 0, beside production:"
for f in $W/c*/log; do echo "  $(basename $(dirname $f)): init $(grep -o 'init [0-9.]*s' $f) | $(grep 'ring-to-ring' $f | tail -3 | grep -oE 'sieve [0-9.]*s pack [0-9.]*s ring-to-ring [0-9.]*s' | tr '\n' '|')"; done
