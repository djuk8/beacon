#!/bin/bash
# fresh_box.sh -- a fresh GPU box from the repo tree to a certified, running hunt, in one supervised pass.
# Written from the first fresh-box test (2026-09-24, 4x RTX 5090): every step below was a stop that day, in this order.
# Usage: bash deploy/fresh_box.sh [--seed SIEVESEED] [--no-launch]     (run as root from the repo root; CUDA 12 toolkit, gcc, python3 with numpy+gmpy2, pari-gp)
# Seeds: k0 = 1e12 + 8e9*seed. box1 used 2004 (k0 1.70e13, walked to ~1.76e13). New boxes: 2500, 3000, 3500 ... (500 apart = 4e12 in k, ~40 box-days each).
set -uo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd); P3=$HOME/beacon/p3; K=$P3/o1_kit; R=$HOME/beacon/raid610; SEED=2500; LAUNCH=1
while [ $# -gt 0 ]; do case $1 in --seed) SEED=$2; shift;; --no-launch) LAUNCH=0;; esac; shift; done
say(){ echo "$(date -u +%FT%TZ) fresh_box: $*"; }; die(){ say "FAIL: $*"; exit 1; }
# 0. prerequisites
for t in nvcc gcc git nvidia-smi gp; do command -v $t >/dev/null || die "$t not on PATH (CUDA toolkit / build-essential / git / pari-gp)"; done
PY=$(command -v /venv/main/bin/python3 || command -v python3); $PY -c "import numpy, gmpy2" 2>/dev/null || die "python needs numpy and gmpy2: $PY -m pip install numpy gmpy2"
[ -x /venv/main/bin/python3 ] || { mkdir -p /venv/main/bin && ln -sf "$(command -v python3)" /venv/main/bin/python3; say "no /venv/main/bin/python3: linked $(command -v python3) (the kit scripts use that path)"; }
CC=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d .); NG=$(nvidia-smi -L | wc -l); [ "$NG" -ge 1 ] || die "no GPU"; say "GPUs $NG, sm_$CC"
# 1. kit and theater
KIT=$(ls "$REPO"/deploy/kit_v8/o1_kit_v8.*.tgz | sort -V | tail -1); [ -n "$KIT" ] || die "no kit tarball in deploy/kit_v8/"
mkdir -p "$P3" "$R"; rm -rf "$K"; tar xzf "$KIT" -C "$P3" || die "kit extract"; [ -d "$K" ] || die "kit tarball must contain a top-level o1_kit/ directory"
for f in resonance_map.py ladder_crown.json g1_fermat_v3.cu onstart_raid_v2.sh go_crown.sh daily.sh harvest_hourly.sh; do [ -f "$K/$f" ] || cp "$REPO"/tools/$f "$K/" 2>/dev/null || cp "$REPO"/theater/raid610/$f "$K/" 2>/dev/null || cp "$REPO"/cuda/$f "$K/" 2>/dev/null; [ -f "$K/$f" ] || die "kit file missing: $f"; done
cp "$K/resonance_map.py" "$K/ladder_crown.json" "$R/"; say "kit $(basename $KIT) -> $K ($(ls $K | wc -l) files); theater $R"
# 2. the GPU driver: CGBN as a sibling of the source directory (the .cu includes ../CGBN/... relative to itself)
[ -d "$P3/CGBN" ] || git clone -q --depth 1 https://github.com/NVlabs/CGBN "$P3/CGBN" || die "git clone CGBN"
mkdir -p "$P3/cuda" && cp "$K/g1_fermat_v3.cu" "$P3/cuda/" && ( cd "$P3/cuda" && nvcc -O3 -arch=sm_$CC -I ../CGBN/include -o ../g1_fermat_v3 g1_fermat_v3.cu -lgmp 2>&1 | grep -iv warning | tail -3 ); [ -x "$P3/g1_fermat_v3" ] || die "g1_fermat_v3 build (nvcc sm_$CC, CGBN, -lgmp)"
"$P3/g1_fermat_v3" --help 2>&1 | grep -q usage || die "g1_fermat_v3 does not run"; say "driver built: $(sha256sum $P3/g1_fermat_v3 | cut -c1-12)"
# 3. seed knob, then go_crown does the rest: venue files, residue cache (~15 min), C/CUDA sieve builds, G-L2 gate, crontab, launch
echo "$SEED" > "$R/SIEVESEED.txt"; say "sieve seed $SEED (k0 = $((10**12 + 8*10**9*SEED)))"
[ "$LAUNCH" = 1 ] || { say "--no-launch: stopping before go_crown (run it yourself from $R: bash $K/go_crown.sh)"; exit 0; }
cd "$R" && bash "$K/go_crown.sh" 2>&1 | tail -8
( crontab -l 2>/dev/null; echo "17 * * * * $K/harvest_hourly.sh >> $R/harvest.log 2>&1" ) | sort -u | crontab -
say "launched. In 20 minutes: bash $K/daily.sh  (fresh box ramps for ~1 h; healthy = ~11k w/s per RTX 5090, GPUs 100%, fallback 0)"
