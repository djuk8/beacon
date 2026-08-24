#!/bin/bash
# gate_r4.sh v1.1 (free-space check; SKIP_BUILD=1; v3 rc checked)
# gate_r4.sh v1.0 -- in-driver early exit (g1_fermat_v3) gates (C, 2026-08-22).  Box1, one quiet card.
#   R0 build v3 (nvcc, gencodes sm_89+sm_120+PTX; CGBN cloned to ~/beacon/CGBN if absent)
#   R1 legacy path identity: v3 (no --ee) vs certified v2 on a real 2048-bit fossil ring -> byte-identical
#   R2 early-exit identity: v3 --ee vs ee_serve(v2) on the fossils AND on a fresh 40-ring mega-ring -> byte-identical
#   R3 throughput: v3 --ee on the 40-ring mega-ring (one process) vs the feeder path (S5: 65 s / 21.8M tests)
# MODE=cpu (sandbox): uses prebuilt CPU backends V2/V3 and small synthetic rings; no nvcc.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); W=${W:-/tmp/gate_r4}; LOG=$W/gate_r4.log; PY=${PY:-python3}
MODE=${MODE:-gpu}; GPU=${GPU:-0}; P3=${P3:-$HOME/beacon/p3}; V2=${V2:-$P3/g1_fermat_v2}; V3=${V3:-$P3/g1_fermat_v3}
CHUNK=${CHUNK:-8}; GROWTH=${GROWTH:-1.5}; N5=${N5:-40}; SCANHUNT=${SCANHUNT:-$HOME/beacon/raid610/scanhunt_v0.py}
FIXTURES=${FIXTURES:-}
rm -rf "$W"; mkdir -p "$W"; need=$(( ${N5:-40} * 600 )); avail=$(df -m "$W" | awk 'NR==2{print $4}'); [ "$avail" -gt "$need" ] || { echo "need ~${need} MB free under $W (have ${avail}); set W= to a big filesystem"; exit 1; }
say(){ echo "$@" | tee -a "$LOG"; }
say "==== gate_r4 v1.0 $(date -u +%FT%TZ) mode=$MODE gpu=$GPU v2=$V2"
# ---------- R0
if [ "$MODE" = gpu ] && [ "${SKIP_BUILD:-0}" = 1 ] && [ -x "$V3" ]; then say "R0: skipped (SKIP_BUILD=1, using $V3 $(sha256sum "$V3" | cut -c1-12))"
elif [ "$MODE" = gpu ]; then
  say "--- R0 build g1_fermat_v3 ---"
  NVCC=$(command -v nvcc || ls /usr/local/cuda/bin/nvcc 2>/dev/null | head -1); [ -n "$NVCC" ] || { say "R0: nvcc not found"; exit 1; }
  [ -d "$P3/../CGBN/include/cgbn" ] || { say "  cloning CGBN -> $P3/../CGBN"; git clone -q --depth 1 https://github.com/NVlabs/CGBN.git "$P3/../CGBN" || { say "R0: CGBN clone failed"; exit 1; }; }
  cp "$HERE/g1_fermat_v3.cu" "$P3/g1_fermat_v3.cu"
  CCBIN=$(command -v g++-12 >/dev/null 2>&1 && echo "-ccbin g++-12" || echo "")
  ( cd "$P3" && $NVCC -O3 $CCBIN ${NVCCFLAGS:-} ${GENCODE:--gencode arch=compute_89,code=sm_89 -gencode arch=compute_120,code=sm_120 -gencode arch=compute_120,code=compute_120} -I../CGBN/include g1_fermat_v3.cu -o g1_fermat_v3 -lgmp ) > "$W/build.log" 2>&1 \
    || { say "R0: build failed: $(grep -m3 error "$W/build.log")"; say "  (if only 'unsupported compiler': rerun with NVCCFLAGS=-allow-unsupported-compiler)"; exit 1; }
  say "  built $V3 $(sha256sum "$V3" | cut -c1-12)  src $(sha256sum "$HERE/g1_fermat_v3.cu" | cut -c1-12)  v2 $(sha256sum "$V2" | cut -c1-12)"
  say "R0: PASS"
fi
export CUDA_VISIBLE_DEVICES=$GPU
run2(){ "$V2" "$@" 2>>"$W/drv.log"; }; run3(){ "$V3" "$@" 2>>"$W/drv.log"; }
# ---------- rings for the gates
mkdir -p "$W/rings"; RINGS=()
if [ "$MODE" = cpu ]; then
  $PY "$HERE/mkrings.py" "$W/rings" --n 3 --ks 40 --S 30 --bits 2048 --bid0 8001 >/dev/null || exit 1
  for b in "$W"/rings/sc_r01_[0-9][0-9][0-9][0-9].bin; do RINGS+=("${b%.bin}"); done
else
  i=0; for f in $FIXTURES; do i=$((i+1)); s="$W/rings/fx_$i"; ln -s "$f" "$s.bin"; ln -s "${f%.bin}.manifest.json" "$s.manifest.json"; RINGS+=("$s"); done
  [ ${#RINGS[@]} -gt 0 ] || { say "need FIXTURES='a.bin b.bin' (2048-bit fossils with manifests)"; exit 1; }
fi
# ---------- R1 legacy identity on the first ring
say "--- R1 legacy path: v3 vs v2 on ${RINGS[0]} ---"
run2 "${RINGS[0]}.bin" "$W/r1_v2.v.bin" && run3 "${RINGS[0]}.bin" "$W/r1_v3.v.bin" && cmp -s "$W/r1_v2.v.bin" "$W/r1_v3.v.bin" && say "R1: PASS (byte-identical, $(grep -c . "$W/drv.log") driver lines)" || { say "R1: FAIL"; exit 1; }
# ---------- R2 early-exit identity per ring: v3 --ee vs ee_serve(v2)
say "--- R2 early-exit identity on ${#RINGS[@]} ring(s) ---"
Q=$W/q; mkdir -p "$Q/req"; ok=1
for s in "${RINGS[@]}"; do
  $PY "$HERE/mksizes.py" "$s.sizes.bin" "$s.manifest.json" >/dev/null
  run3 "$s.bin" "$s.ee3.v.bin" --ee "$s.sizes.bin" --chunk "$CHUNK" --growth "$GROWTH" || { say "  v3 --ee failed on $s"; ok=0; continue; }
  printf '{"bin":"%s","out":"%s","seed":1,"round":1,"bid":"1"}\n' "$s.bin" "$s.serve.v.bin" > "$Q/req/$(basename "$s").json"
  $PY "$HERE/ee_serve.py" --queue "$Q" --gpu "$GPU" --driver "$V2" --kwin 1 --tmax 1 --workers 1 --lock "$W/lock" --chunk "$CHUNK" --growth "$GROWTH" --once >> "$W/serve.log" 2>&1
  cmp -s "$s.ee3.v.bin" "$s.serve.v.bin" && say "  $(basename "$s"): IDENTICAL  $(grep -h 'g1_fermat\[EE\]' "$W/drv.log" | tail -1 | sed 's/.*ks=/ks=/')" || { say "  $(basename "$s"): DIFFER"; ok=0; }
done
[ $ok -eq 1 ] && say "R2: PASS" || { say "R2: FAIL"; exit 1; }
# ---------- R2b + R3: fresh 40-ring mega-ring (gpu mode only)
if [ "$MODE" = gpu ] && [ -f "$SCANHUNT" ]; then
  say "--- R2b/R3: $N5 fresh rings -> one mega-ring: identity vs ee_serve(v2) and throughput ---"
  mkdir -p "$W/mk"; MARGS="--zd 1439 --swap 2 3 5 7 11 --kdig 13 --merit 37.8241 --Q 100000 --deep-q 0 --deep-from-ring 99 --rings 1568,4374,7244,10198,13500,17734,26542 --bits 2048 --kblock 20000"
  for s5 in $(seq 9201 $((9200+N5))); do ( mkdir -p "$W/mk/hunt_s$s5" && cd "$W/mk/hunt_s$s5" && $PY "$SCANHUNT" make --round 1 $MARGS --seed $s5 >make.log 2>&1 ) & done; wait
  BINS=$(ls "$W"/mk/hunt_s*/sc_r01_[0-9][0-9][0-9][0-9].bin); MANS=$(for b in $BINS; do echo "${b%.bin}.manifest.json"; done)
  $PY - "$W/mega" $BINS <<'PY'
import sys, struct
out, bins = sys.argv[1], sys.argv[2:]; tot = 0; bits = None; bodies = []
for b in bins:
    d = open(b, "rb").read(); mg, bt, n = struct.unpack("<IIQ", d[:16]); bits = bits or bt; tot += n; bodies.append(d[16:])
with open(out + ".bin", "wb") as f:
    f.write(struct.pack("<IIQ", 0x31433247, bits, tot)); [f.write(x) for x in bodies]
print(f"mega-ring: {len(bins)} rings, {tot} candidates")
PY
  $PY "$HERE/mksizes.py" "$W/mega.sizes.bin" $MANS | tee -a "$LOG"
  t0=$(date +%s.%N); run3 "$W/mega.bin" "$W/mega.ee3.v.bin" --ee "$W/mega.sizes.bin" --chunk "$CHUNK" --growth "$GROWTH" || { say "R3: v3 --ee FAILED: $(tail -1 "$W/drv.log")"; exit 1; }; t3=$(echo "$(date +%s.%N) - $t0" | bc)
  say "  v3 --ee mega-ring: $(grep -h 'g1_fermat\[EE\]' "$W/drv.log" | tail -1 | sed 's/.*count=/count=/')  process wall ${t3}s"
  rm -rf "$Q"; mkdir -p "$Q/req"; for b in $BINS; do printf '{"bin":"%s","out":"%s","seed":1,"round":1,"bid":"1"}\n' "$b" "${b%.bin}.serve.v.bin" > "$Q/req/$(basename "$(dirname "$b")").json"; done
  t0=$(date +%s.%N); $PY "$HERE/ee_serve.py" --queue "$Q" --gpu "$GPU" --driver "$V2" --kwin 400000 --tmax 5 --workers 1 --lock "$W/lock" --chunk "$CHUNK" --growth "$GROWTH" --once >> "$W/serve.log" 2>&1; tf=$(echo "$(date +%s.%N) - $t0" | bc)
  say "  ee_serve(v2) same rings: $(grep -E 'rings,.*launches' "$W/serve.log" | tail -1 | sed 's/.*ee_serve: //')  process wall ${tf}s"
  $PY - "$W/mega.ee3.v.bin" $BINS <<'PY' | tee -a "$LOG"
import sys, struct
mega = open(sys.argv[1], "rb").read()[16:]; off = 0; bad = 0
for b in sys.argv[2:]:
    v = open(b[:-4] + ".serve.v.bin", "rb").read(); n = struct.unpack("<IIQ", v[:16])[2]
    if mega[off:off + n] != v[16:]: bad += 1
    off += n
print(f"  R2b: {len(sys.argv)-2} rings compared, {bad} differ -> {'PASS' if not bad else 'FAIL'}"); sys.exit(1 if bad else 0)
PY
  [ $? -eq 0 ] || { say "R2b: FAIL"; exit 1; }
  say "R3: in-driver early exit wall ${t3}s vs feeder path ${tf}s on the same $N5 rings (x$(echo "scale=2; $tf/$t3" | bc))"
fi
say "==== gate_r4: ALL PASS"
