#!/bin/bash
# o1_gates.sh v1.5 -- O1 gate runner for box1 (C, 2026-08-21).
# v1.4 -> v1.5: G3 THEATER CROSS-CHECK -- three independent reads of the box
# rate (v.bin verdict files per 10 min -> tests/s; 20 s sampler of concurrent
# driver processes; load average vs cores), because the manifest count said
# 249 w/s against an R1 of 14,500 and one read is not a verdict.
# v1.3 -> v1.4: G3 reads the LIVE THEATER RATE (manifests per rung in the last
# 10 min, read-only) -> windows/s, launches/s, candidates per launch per rung,
# GPU-busy and launch-init fractions; models the per-card feeder WITHOUT early
# exit (legacy ladder, batched launches) and WITH it, so S4 compares both.
# v1.2 -> v1.3 (after the second real run): G1 runs under CUDA_MODULE_LOADING=LAZY
# (measured 469 vs 1043 ms cold start) and parses stage E into a serialised
# per-launch init cost (ser_ms); G3 models the 2048-bit raid ALWAYS from the
# 2048-bit numbers (the 16k-bit fixture had hijacked it), takes the production
# ring W0 and shell S from the 2nd-newest LIVE r01 manifest, and adds the
# serialised-launch constraint to the mega-ring sizing.
# v1.1 -> v1.2 (after the first real box1 run): G1 carries STAGES through and
# parses the v1.3 harness (knee from driver-internal timing, single-test
# latency); G3 rewritten -- the per-loop wave model is dead on the measured
# numbers (cold 1.18 s, latency-bound kernel), so G3 now sizes the AGGREGATED
# pipeline (mega-rings per card, chunk schedule, in-flight, RAM, feed, gain).
# v1.0 -> v1.1: ee_drive.py ships IN the kit (EE defaults to the kit copy);
# G0 samples GPU utilisation over 10 s, maps loops -> GPU via their
# CUDA_VISIBLE_DEVICES, lists compute apps per GPU, prints the FULL driver
# sha (grep it on shredder against kit_v1/LINEAGE to bind CERT_SHA);
# kit-hash check inverted under pipefail in v1.0 (reported OK on mismatch) -- fixed.
# One runner, one log, one paste.  State-file skip; a gate is marked ONLY on
# success; rerun = resume.  Read-only on the live theater (fossils copied to
# /tmp, nothing shipped to a seed).  The only action on live processes is the
# explicit "drill" subcommand, and it asks for YES.
#
#   bash o1_gates.sh            # run G0..G3 in order, stop at first red
#   bash o1_gates.sh status     # state + log tail
#   bash o1_gates.sh G2         # (re)run one gate (FORCE=1 to rerun a green one)
#   bash o1_gates.sh drill      # fire drill: kill one seed, time the watchdog
#   bash o1_gates.sh reset      # forget state (asks)
#
# Gates:  G0 preflight (kit hashes, venv+gmpy2, driver hash vs cert, ee_drive,
#            MAGIC grep, GPU pick, soak read)     -- no GPU work
#         G1 G-O1 harness A+B+C+D (gate_o1.sh v1.2)   -- ~5 min on one card
#         G2 replay x3 fossil trios (replay_compare.py) -- ~2 min
#         G3 geometry + feed model from G1/G2 numbers  -- zero-meter
# Env (all optional): PY DRV EE GPU CERT_SHA KIT_MANIFEST FOSSIL_ROOT FIXTURES
#     MAKE_S(7) BETA(0.01744) CHUNK(8) DRILL_PATTERN(raid_loop) FORCE(0)
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
P3=${P3:-~/beacon/p3}; P3=${P3/#\~/$HOME}; mkdir -p "$P3"
LOG=${LOG:-$P3/o1_gates.log}; STATE=${STATE:-$P3/o1_gates.state}; touch "$STATE"
DRV=${DRV:-$P3/g1_fermat_v2}; DRV=${DRV/#\~/$HOME}
EE=${EE:-}; [ -z "$EE" ] && { [ -f "$HERE/ee_drive.py" ] && EE=$HERE/ee_drive.py || EE=$P3/ee_drive.py; }; EE=${EE/#\~/$HOME}
if [ -z "${PY:-}" ]; then [ -x /venv/main/bin/python3 ] && PY=/venv/main/bin/python3 || PY=python3; fi
GPU=${GPU:-}; CERT_SHA=${CERT_SHA:-}; KIT_MANIFEST=${KIT_MANIFEST:-}
FOSSIL_ROOT=${FOSSIL_ROOT:-$HOME}; FIXTURES=${FIXTURES:-}
MAKE_S=${MAKE_S:-7}; BETA=${BETA:-0.01744}; CHUNK=${CHUNK:-8}; STAGES=${STAGES:-ABCD}; export CUDA_MODULE_LOADING=${CUDA_MODULE_LOADING:-LAZY}
[ -n "${RING_W:-}" ] && RING_W_SET=1; RING_W=${RING_W:-840}; LOOP_WS=${LOOP_WS:-120}; RING_S=${RING_S:-0}; THEATER_DIR=${THEATER_DIR:-$HOME/beacon/raid610}   # RING_S = production shell (tests/k at rung 1); 0 = take the fixture's median; production ring (windows/make) [MODEL: read off a raid manifest]; windows/s per loop (R1: 14.5k/121)
DRILL_PATTERN=${DRILL_PATTERN:-raid_loop}; FORCE=${FORCE:-0}
say(){ echo "$@" | tee -a "$LOG"; }
hr(){ say "------------------------------------------------------------------"; }
stamp(){ date -u +'%FT%TZ'; }
done_(){ grep -q "^$1 PASS" "$STATE"; }
mark(){ echo "$1 PASS $(stamp) ${2:-}" >> "$STATE"; say ">> $1 PASS  ${2:-}"; }
detail(){ grep "^$1 PASS" "$STATE" | tail -1 | sed -n "s/.*[[:space:]]$2=\([^ ]*\).*/\1/p"; }
shortsha(){ sha256sum "$1" | cut -c1-16; }
run_gate(){  # $1 gate  $2 function
  local g=$1 fn=$2
  if done_ "$g" && [ "$FORCE" != "1" ]; then say "== $g already PASS ($(grep "^$g PASS" "$STATE" | tail -1 | cut -d' ' -f3-)) -- skip (FORCE=1 to rerun)"; return 0; fi
  hr; say "== $g  $(stamp)  runner v1.5 $(shortsha "$0")"; $fn; local rc=$?
  if [ $rc -ne 0 ]; then say ">> $g RED (rc=$rc) -- stopped. Fix, then rerun: bash $0"; return $rc; fi
}
pick_gpu(){
  if [ -n "$GPU" ]; then echo "$GPU"; return; fi
  if command -v nvidia-smi >/dev/null; then
    nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader,nounits | sed 's/,//' | sort -k2 -n | head -1 | cut -d' ' -f1
  else echo 0; fi
}

# ------------------------------------------------------------------ G0
g0(){
  say "host=$(hostname) kernel=$(uname -r) nproc=$(nproc) user=$(id -un) P3=$P3"
  say "kit files:"; local ok=1
  if [ -f "$HERE/o1_kit.sha256" ]; then
    local chk; chk=$(cd "$HERE" && sha256sum -c o1_kit.sha256 2>&1); echo "$chk" >> "$LOG"
    if echo "$chk" | grep -vq ': OK$'; then say "G0: kit hash mismatch (re-upload the tarball):"; echo "$chk" | grep -v ': OK$' | sed 's/^/    /' | tee -a "$LOG"; ok=0
    else say "  kit hashes OK ($(wc -l < "$HERE/o1_kit.sha256") files)"; fi
  else say "  o1_kit.sha256 missing beside the runner (uploaded by hand?) -- continuing"; fi
  say "python: $PY ($($PY -c 'import sys;print(sys.version.split()[0])' 2>&1))"
  if ! $PY -c 'import gmpy2' 2>/dev/null; then
    say "  gmpy2 absent in $PY -- installing (pip) ..."; $PY -m pip install -q gmpy2 2>&1 | tail -2 | tee -a "$LOG"
    $PY -c 'import gmpy2;print("  gmpy2",gmpy2.version())' 2>&1 | tee -a "$LOG" || { say "G0: gmpy2 unavailable -- the harness cannot build known answers. STOP."; ok=0; }
  else say "  gmpy2 $($PY -c 'import gmpy2;print(gmpy2.version())')"; fi
  if [ -x "$DRV" ]; then say "driver: $DRV size=$(stat -c%s "$DRV")"; say "  sha256 FULL: $(sha256sum "$DRV" | cut -d' ' -f1)   (on shredder: grep -rl <this> ~/lab/deploy/kit_v1 ~/lab/beacon/LINEAGE.md -> then CERT_SHA=<this>)"; else say "G0: driver not executable at $DRV (set DRV=)"; ok=0; fi
  if [ -z "$CERT_SHA" ]; then
    local mf=${KIT_MANIFEST:-}; [ -z "$mf" ] && mf=$(grep -rlsE 'g1_fermat_v2' "$HOME"/beacon/deploy "$HOME"/kit* "$P3" 2>/dev/null | grep -iE 'manifest|sha256|\.sum' | head -1 || true)
    [ -n "$mf" ] && CERT_SHA=$(grep -E 'g1_fermat_v2' "$mf" | grep -oE '[0-9a-f]{64}' | head -1 || true)
    [ -n "$CERT_SHA" ] && say "  cert hash from $mf: ${CERT_SHA:0:16}" || say "  cert hash: NOT FOUND (set CERT_SHA= or KIT_MANIFEST=) -- G1 runs UNBOUND to the certificate"
  fi
  if [ -n "$CERT_SHA" ] && [ -x "$DRV" ]; then
    [ "$(sha256sum "$DRV" | cut -d' ' -f1)" = "$CERT_SHA" ] && say "  driver == certified binary" || { say "G0: driver hash != CERT_SHA -- not the certified binary. STOP."; ok=0; }
  fi
  if [ -f "$EE" ]; then say "ee_drive: $EE sha=$(shortsha "$EE")"; say "  MAGIC in ee_drive: $(grep -oE 'MAGIC_[CV][A-Za-z_]* *[=:,] *0x[0-9a-fA-F]+|0x3143324[0-9a-fA-F]|0x3156324[0-9a-fA-F]' "$EE" | sort -u | tr '\n' ' ' | cut -c1-160)"
    local cu; cu=$(ls "$HOME"/beacon/cuda/g1_fermat_v2.cu "$P3"/g1_fermat_v2.cu 2>/dev/null | head -1 || true)
    [ -n "$cu" ] && say "  MAGIC in driver source $cu: $(grep -oE 'MAGIC_[CV][A-Za-z_]* *[=:,] *0x[0-9a-fA-F]+|0x3143324[0-9a-fA-F]|0x3156324[0-9a-fA-F]' "$cu" | sort -u | tr '\n' ' ' | cut -c1-160)" || say "  driver source not found here (MAGIC cross-check by eye: C=0x31433247 V=0x31563247)"
    grep -qE '0x31433247|MAGIC_C' "$EE" || say "  WARN: ee_drive does not mention MAGIC_C -- read it before G1"
  else say "G0: ee_drive not found at $EE (set EE=)"; ok=0; fi
  if command -v nvidia-smi >/dev/null; then
    say "gpus (utilisation = mean of 5 samples over 10 s):"
    local samp; samp=$(for i in 1 2 3 4 5; do nvidia-smi --query-gpu=index,utilization.gpu,memory.used,temperature.gpu --format=csv,noheader,nounits; sleep 2; done)
    echo "$samp" | awk -F', *' '{u[$1]+=$2; m[$1]=$3; t[$1]=$4; c[$1]++} END{for(i in u) printf "  gpu %s: util %.0f%%  mem %s MiB  temp %sC\n", i, u[i]/c[i], m[i], t[i]}' | sort | tee -a "$LOG"
    say "  compute apps per gpu (pid count):"; nvidia-smi --query-compute-apps=gpu_bus_id,pid --format=csv,noheader | awk -F', *' '{n[$1]++} END{for(b in n) printf "    %s: %d procs\n", b, n[b]}' | tee -a "$LOG"
    say "  loops by CUDA_VISIBLE_DEVICES (from /proc/<pid>/environ of '$DRILL_PATTERN'):"
    for p in $(pgrep -f "$DRILL_PATTERN"); do tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -m1 '^CUDA_VISIBLE_DEVICES=' || echo "CUDA_VISIBLE_DEVICES=<unset>"; done | sort | uniq -c | sed 's/^/    /' | tee -a "$LOG"
  else say "  nvidia-smi not found (dry run?)"; fi
  GPU=$(pick_gpu); say "  gate GPU = $GPU (least loaded unless GPU= set)"
  say "soak read (informational):"
  say "  loops alive ($DRILL_PATTERN): $(pgrep -fc "$DRILL_PATTERN")   ee_drive alive: $(pgrep -fc ee_drive)"
  if [ -f /root/watchdog.log ]; then
    say "  watchdog.log lines=$(wc -l < /root/watchdog.log) mtime=$(date -u -r /root/watchdog.log +%FT%TZ) -- last 5 lines:"; tail -n 5 /root/watchdog.log | cut -c1-160 | sed 's/^/    /' | tee -a "$LOG"
    [ -f /root/onstart_raid.sh ] && say "  onstart_raid.sh sha=$(shortsha /root/onstart_raid.sh); crontab: $(crontab -l 2>/dev/null | grep -c onstart) line(s) mention onstart"
  else say "  /root/watchdog.log not present here"; fi
  [ $ok -eq 1 ] && mark G0 "py=$PY gpu=$GPU cert=${CERT_SHA:0:12}${CERT_SHA:+} drv=$(shortsha "$DRV") ee=$(shortsha "$EE")" || return 1
}

# ------------------------------------------------------------------ G1
g1(){
  [ -n "$GPU" ] || GPU=$(detail G0 gpu); [ -n "$GPU" ] || GPU=$(pick_gpu)
  [ -f "$HERE/gate_o1.sh" ] || { say "G1: gate_o1.sh missing beside runner"; return 1; }
  local fx bits2=""; fx=$(detail G2 fixture)
  [ -n "$fx" ] && [ -f "$fx" ] && bits2=$($PY -c "import struct,sys;print(struct.unpack('<IIQ',open(sys.argv[1],'rb').read(16))[1])" "$fx") && [ "$bits2" = "2048" ] && bits2=""
  bits2=${D_BITS2:-$bits2}
  say "running gate_o1.sh v1.3 stages=$STAGES on GPU $GPU (~3-5 min for ABCD${bits2:+; D also at production bits=$bits2 from the G2 fixture})"
  local glog=$P3/gate_o1.log
  PY=$PY DRV=$DRV EE=$EE GPU=$GPU CERT_SHA=$CERT_SHA CHUNK=$CHUNK STAGES=$STAGES D_BITS2=$bits2 LOG=$glog bash "$HERE/gate_o1.sh" 2>&1 | tee -a "$LOG" | grep -E '^(A|B|C|D|E|k[0-9]|D\[[0-9]+\]):|PASS|FAIL|STOP|sha256' | sed 's/^/  /'
  local rc=${PIPESTATUS[0]}
  local cold knee peak lat knee2 peak2 lat2 mps
  cold=$(grep -E '^C: rcs' "$glog" | tail -1 | sed -n 's/.*trimmed mean \([0-9]*\) ms.*/\1/p')
  knee=$(grep -E '^D\[2048\]: peak' "$glog" | tail -1 | sed -n 's/.*of peak = \([0-9]*\);.*/\1/p')
  peak=$(grep -E '^D\[2048\]: peak' "$glog" | tail -1 | sed -n 's/.*: peak \([0-9]*\) t\/s.*/\1/p')
  lat=$(grep -E '^D\[2048\]: peak' "$glog" | tail -1 | sed -n 's/.*latency ~\([0-9]*\) ms.*/\1/p')
  if [ -n "$bits2" ]; then
    knee2=$(grep -E "^D\[$bits2\]: peak" "$glog" | tail -1 | sed -n 's/.*of peak = \([0-9]*\);.*/\1/p')
    peak2=$(grep -E "^D\[$bits2\]: peak" "$glog" | tail -1 | sed -n 's/.*: peak \([0-9]*\) t\/s.*/\1/p')
    lat2=$(grep -E "^D\[$bits2\]: peak" "$glog" | tail -1 | sed -n 's/.*latency ~\([0-9]*\) ms.*/\1/p')
  fi
  mps=$(grep -E '^E: MPS cold-start' "$glog" | tail -1 | sed -n 's/.*median \([0-9]*\) ms.*/\1/p')
  local ser sermps
  ser=$(grep -E '^E: no-MPS: 8 concurrent' "$glog" | tail -1 | $PY -c "import sys,re;l=sys.stdin.read();m=re.search(r'wall ([0-9.]+) s.*max internal ([0-9.]+) s',l);print(int((float(m.group(1))-float(m.group(2)))/8*1000) if m else '')")
  sermps=$(grep -E '^E: MPS: 8 concurrent' "$glog" | tail -1 | $PY -c "import sys,re;l=sys.stdin.read();m=re.search(r'wall ([0-9.]+) s.*max internal ([0-9.]+) s',l);print(int((float(m.group(1))-float(m.group(2)))/8*1000) if m else '')")
  [ -n "$ser" ] && say "E-derived: serialised init per launch ~${ser} ms (no MPS), ~${sermps:-?} ms (MPS) = (8-concurrent wall - longest kernel)/8"
  say "parsed: cold_ms=${cold:-?} 2048-bit: knee=${knee:-?} peak=${peak:-?} lat_ms=${lat:-?}${bits2:+  ${bits2}-bit: knee=${knee2:-?} peak=${peak2:-?} lat_ms=${lat2:-?}}${mps:+  mps_cold_ms=$mps}"
  [ $rc -eq 0 ] && [ -n "$cold" ] && [ -n "$knee" ] && [ -n "$lat" ] && mark G1 "gpu=$GPU stages=$STAGES lazy=$CUDA_MODULE_LOADING cold_ms=$cold knee=$knee peak=$peak lat_ms=$lat bits2=${bits2:-2048} knee2=${knee2:-$knee} peak2=${peak2:-$peak} lat2_ms=${lat2:-$lat} mps_cold_ms=${mps:--} ser_ms=${ser:--} sermps_ms=${sermps:--}" || { say "G1: harness rc=$rc (2 = STOP/gmpy2; 1 = FAIL) or D unresolved -- read $glog"; return 1; }
}

# ------------------------------------------------------------------ G2
find_fixtures(){  # prints up to 3 fossil stems (bin+v.bin+manifest, older than 5 min), largest first
  if [ -n "$FIXTURES" ]; then for f in $FIXTURES; do echo "${f%.bin}"; done; return; fi
  find "$FOSSIL_ROOT" -maxdepth 7 -type f -name '*.v.bin' -mmin +5 -size +16c 2>/dev/null | while read -r v; do
    s=${v%.v.bin}; [ -f "$s.bin" ] || continue; [ "$(stat -c%s "$s.bin")" -lt 2000000000 ] || continue   # skip >2 GB monsters
    if [ -f "$s.manifest.json" ]; then m="$s.manifest.json"; elif [ -f "$s.json" ]; then m="$s.json"; else continue; fi
    echo "$(stat -c%s "$s.bin") $s $m"
  done | sort -rn | awk '!seen[$2]++' | head -3
}
g2(){
  [ -n "$GPU" ] || GPU=$(detail G1 gpu); [ -n "$GPU" ] || GPU=$(pick_gpu)
  [ -f "$HERE/replay_compare.py" ] || { say "G2: replay_compare.py missing beside runner"; return 1; }
  say "fossil fixtures (bin + v.bin + manifest, -mmin +5, under $FOSSIL_ROOT; FIXTURES= to override):"
  local list; list=$(find_fixtures); [ -n "$list" ] || { say "G2: no fossil trios found under $FOSSIL_ROOT -- set FOSSIL_ROOT=<dir with gl_NNNN.bin/.v.bin/.manifest.json> or FIXTURES='a.bin b.bin c.bin'. STOP."; return 1; }
  echo "$list" | sed 's/^/  /' | tee -a "$LOG"
  local n=0 pass=0 ratios="" walls="" first=""
  while read -r sz stem man; do
    [ -n "$stem" ] || continue; n=$((n+1)); [ -z "$first" ] && first="$stem.bin"
    say "-- replay $n: $stem.bin"
    local out; out=$($PY "$HERE/replay_compare.py" "$stem.bin" ${man:+--man "$man"} --ee "$EE" --driver "$DRV" --gpu "$GPU" --chunk "$CHUNK" --legacy-time --py "$PY" 2>&1); local rc=$?
    echo "$out" >> "$LOG"; echo "$out" | grep -E '^REPLAY (tests|verdict|wall|PASS|FAIL|FAIL|ee_drive rc|ks=)|^REPLAY:' | sed 's/^/  /'
    [ $rc -eq 0 ] && pass=$((pass+1))
    [ $rc -eq 3 ] && say "  (rc=3 = CONTRACT mismatch, not a semantics failure -- read the manifest keys above and fix the harness)"
    ratios="$ratios$(echo "$out" | sed -n 's/.* ratio=\([0-9.]*\) (ideal.*/\1/p' | head -1),"
    walls="$walls$(echo "$out" | sed -n 's/.*wall ratio=\([0-9.]*\) .*/\1/p' | head -1),"
  done <<< "$(echo "$list" | awk '{print $1, $2, $3}')"
  say "replays run=$n pass=$pass test-ratios=$ratios wall-ratios=$walls"; [ $n -lt 3 ] && say "  (fewer than 3 trios found -- fine for the gate, say so in the log)"
  [ $n -ge 1 ] && [ $pass -eq $n ] && mark G2 "n=$n ratios=$ratios walls=$walls fixture=$first" || return 1
}

# ------------------------------------------------------------------ G3
g3(){
  local cold knee peak lat fx bits2 mps ser; cold=$(detail G1 cold_ms); fx=$(detail G2 fixture); bits2=$(detail G1 bits2); mps=$(detail G1 mps_cold_ms); ser=$(detail G1 ser_ms)
  knee=$(detail G1 knee); peak=$(detail G1 peak); lat=$(detail G1 lat_ms)      # raid610 is 2048-bit: always model from the 2048-bit numbers
  [ "$ser" = "-" ] && ser=""
  [ -n "$bits2" ] && [ "$bits2" != "2048" ] && say "note: fixture bits=$bits2 -> knee2=$(detail G1 knee2) peak2=$(detail G1 peak2) t/s lat2=$(detail G1 lat2_ms) ms (for THAT campaign; not used for the 2048-bit raid model below)"
  [ -n "$cold" ] && [ -n "$knee" ] && [ -n "$peak" ] && [ -n "$lat" ] || { say "G3: need G1 v1.3 numbers -- rerun: FORCE=1 STAGES=CDE bash $0 G1"; return 1; }
  local loops gpus; loops=$(pgrep -fc "$DRILL_PATTERN")
  gpus=$(command -v nvidia-smi >/dev/null && nvidia-smi -L | wc -l || echo 1); [ "$gpus" -ge 1 ] || gpus=1
  # production ring size: 2nd-newest manifest written in the last 2 h anywhere under $HOME (live theater, read-only), else RING_W
  local lm; lm=$(find "$HOME" -maxdepth 7 -name '*_r01_*.manifest.json' -mmin -120 2>/dev/null | xargs -r ls -t 2>/dev/null | sed -n 2p)
  if [ -n "$lm" ]; then
    local rw; rw=$($PY -c "import json,sys,statistics;d=json.load(open(sys.argv[1]));print(len(d['sizes']), int(statistics.median(d['sizes'])))" "$lm" 2>/dev/null)
    if [ -n "$rw" ]; then
      [ -z "${RING_W_SET:-}" ] && RING_W=${rw% *}; [ "$RING_S" = "0" ] && RING_S=${rw#* }
      say "production rung-1 ring from live manifest $lm (2nd-newest, era-cut, read-only): W0=${rw% *} ks, shell S=${rw#* } -> RING_W=$RING_W RING_S=$RING_S"
    fi
  else say "no live r01 manifest in the last 2 h -> RING_W=$RING_W RING_S=$RING_S [MODEL unless set]"; fi
  say "THEATER CROSS-CHECK (read-only):"
  find "$THEATER_DIR" -name '*.v.bin' -mmin -10 -printf '%s\n' 2>/dev/null | awk -v tw=121.2 '{t+=$1-16;n++} END{if(n) printf "  v.bin files last 10 min: %d launches, %.0f verdicts -> %.0f tests/s box-wide -> %.0f w/s at t/w %.1f (R1: 14,500)\n", n, t, t/600, t/600/tw, tw; else print "  no .v.bin written in the last 10 min under the theater dir"}' | tee -a "$LOG"
  local cnt=0 i; for i in $(seq 40); do cnt=$((cnt + $(pgrep -c g1_fermat))); sleep 0.5; done
  say "  concurrent driver processes (mean of 40 samples over 20 s): $(awk -v c=$cnt 'BEGIN{printf "%.2f", c/40}')  (R1 pace would be ~launches/s x 1.3 s, i.e. several; <0.5 = starved)"
  say "  load: $(cut -d' ' -f1-3 /proc/loadavg) on $(nproc) cores; make-side processes: $(pgrep -fc fastmake) fastmake, $(pgrep -fc python) python"
  say "inputs: cold_ms=$cold ${bits2:-2048}-bit: knee=$knee peak_tps=$peak test_latency_ms=$lat mps_cold_ms=${mps:--} fixture=${fx:-none} loops_alive=$loops gpus=$gpus nproc=$(nproc) RING_W=$RING_W LOOP_WS=$LOOP_WS BETA=$BETA"
  $PY - "$cold" "$knee" "$peak" "$lat" "${fx:-}" "$loops" "$gpus" "$(nproc)" "$RING_W" "$LOOP_WS" "$BETA" "$RING_S" "$P3/o1_geometry.json" "$(awk '/MemTotal/{printf "%.0f", $2/1048576}' /proc/meminfo)" "2048" "${mps:--}" "${ser:-}" "$THEATER_DIR" <<'PYG' 2>&1 | tee -a "$LOG"
import sys, json, math, os, statistics
cold_ms, knee, peak, lat_ms, fx, loops, gpus, cores, ring_w, loop_ws, beta, ring_s, outp, ram_gb, bits2, mps, ser_ms, theater = sys.argv[1:]
ser = float(ser_ms)/1000 if ser_ms else 0.35   # serialised init per launch; default 0.35 s = box1 E @EAGER [MODEL until E under LAZY]
cold = float(cold_ms)/1000; knee = int(knee); peak = float(peak); lat = float(lat_ms)/1000
loops = int(loops); gpus = int(gpus); cores = int(cores); ring_w = int(ring_w); loop_ws = float(loop_ws); beta = float(beta); ram_gb = float(ram_gb or 64)
S = None
for cand in ((fx[:-4] + ".manifest.json") if fx else "", (fx[:-4] + ".json") if fx else ""):
    if cand and os.path.exists(cand):
        m = json.load(open(cand)); S = int(statistics.median(m["sizes"])); Wfx = len(m["sizes"]); break
if not S: S, Wfx = 144, 0; print("G3: no fixture manifest -> S=144 is a MODEL placeholder (set FIXTURES=)")
if int(ring_s) > 0: print(f"G3: shell overridden RING_S={ring_s} (fixture median was {S})"); S = int(ring_s)
elif Wfx: print(f"G3: NOTE shell S={S} comes from an ARCHIVED fixture, not a production raid ring (rung-1 shell ~1.70/beta = {1.70/beta:.0f}); set RING_S= to use the production value")
tw_leg = 121.2                                   # frozen, measured (CL/beta)
tw_ee1 = 1.0 / beta                              # early exit at chunk 1 over the ladder: every window dies once -> ~1/beta (frozen 57.3)
def Etests(b): return sum((b[w] - b[w-1]) * (1-beta)**b[w-1] for w in range(1, len(b)))
def sched(name, chunks):
    b = [0]
    for c in chunks:
        if b[-1] >= S: break
        b.append(min(S, b[-1] + c))
    while b[-1] < S: b.append(min(S, b[-1] + chunks[-1]))
    return name, b
def grow(c0, g, n=64):
    out, c = [], c0
    for _ in range(n): out.append(max(1, int(round(c)))); c *= g
    return out
E1 = Etests(list(range(S + 1)))                  # chunk-1 expectation at this shell
schedules = [sched("const 8", [8]*64), sched("const 16", [16]*64), sched("const 32", [32]*64),
             sched("grow x1.5 from 8", grow(8, 1.5)), sched("grow x2 from 8", grow(8, 2.0)),
             sched("3-wave", [max(1, S//6), max(1, S//3), S]), sched("2-wave", [max(1, S//3), S])]
cores_card = cores / gpus; loops_card = loops / gpus if loops else cores_card
feed_now = loops_card * loop_ws; feed_max = cores_card * loop_ws          # w/s per card from the make side (measured loop rate)
app_leg = peak / tw_leg
print(f"G3 measured @{bits2} bits (LAZY): cold {cold*1000:.0f} ms/launch (MPS: {mps} ms), serialised init {ser*1000:.0f} ms/launch, knee {knee} cands/launch, peak {peak:,.0f} t/s, single-test latency {lat*1000:.0f} ms (in-flight for peak ~{peak*lat:,.0f}); fixture shell S={S} (ring of {Wfx} ks); production ring RING_W={ring_w} [MODEL], {loop_ws:.0f} w/s per loop (R1)")
print(f"G3 PER-LOOP WAVES (drop-in replacement of raid_loop): wave batch 8 x {ring_w} = {8*ring_w:,} vs knee {knee} -> occupancy {min(1, 8*ring_w/knee):.0%}; "
      f"{math.ceil(S/8)} launches x {cold*1000:.0f} ms = {math.ceil(S/8)*cold:.1f} s latency per ring vs a ~{ring_w/loop_ws:.1f} s cycle -> loop throughput x{(ring_w/loop_ws)/(ring_w/loop_ws - cold + math.ceil(S/8)*cold):.2f}.  "
      + ("DEAD." if 8*ring_w < 0.5*knee or math.ceil(S/8)*cold > ring_w/loop_ws else "marginal."))
print(f"G3 LEGACY: 1 launch/ring of {ring_w*S:,} cands ({'>=' if ring_w*S >= knee else '< !!'} knee); cold start = {cold/(ring_w/loop_ws)*100:.0f}% of each loop cycle (persistence mode fix would return that for free [MODEL]); "
      f"card appetite {app_leg:,.0f} w/s, feed now {feed_now:,.0f} w/s ({loops_card:.0f} loops/card), feed max {feed_max:,.0f} w/s ({cores_card:.0f} cores/card)")
# ---- live theater rate (read-only; manifests written in the last 10 min, grouped by rung) ----
import glob, re, time, collections
now = time.time(); byr = collections.defaultdict(list)
for p in glob.glob(os.path.join(theater, "**", "*_r0[0-9]_*.manifest.json"), recursive=True):
    try:
        if now - os.path.getmtime(p) <= 600: byr[re.search(r"_(r0[0-9])_", p).group(1)].append(p)
    except Exception: pass
th = {}
if byr:
    print(f"G3 THEATER (last 10 min under {theater}, {sum(len(v) for v in byr.values())} manifests):")
    print(f"{'rung':>5} {'rings/10min':>11} {'ks/ring':>8} {'cands/launch':>12} {'launch/s/card':>13} {'gpu s/s/card':>12} {'init s/s/card':>13}")
    tot_l = tot_g = 0.0
    for r in sorted(byr):
        ps = byr[r]; ks = []; cs = []
        for p in ps[:40]:
            try: d = json.load(open(p)); ks.append(len(d["sizes"])); cs.append(sum(d["sizes"]))
            except Exception: pass
        if not ks: continue
        n10 = len(ps); lps = n10 / 600 / gpus; gss = lps * statistics.mean(cs) / peak; iss = lps * cold
        tot_l += lps; tot_g += gss
        th[r] = dict(rings10=n10, ks=statistics.mean(ks), cands=statistics.mean(cs), launch_s=lps)
        print(f"{r:>5} {n10:11d} {statistics.mean(ks):8.0f} {statistics.mean(cs):12.0f} {lps:13.2f} {gss:12.3f} {iss:13.2f}")
    if "r01" in th:
        ws_box = th["r01"]["rings10"] * th["r01"]["ks"] / 600
        print(f"G3 THEATER RATE: {ws_box:,.0f} windows/s box-wide now (R1 certified 14,500); per card: launches {tot_l:.2f}/s, GPU busy {tot_g:.2f} (model at peak {peak:,.0f} t/s), launch init {tot_l*cold:.2f} s per s"
              + ("  -> the card is mostly waiting on launches, not testing" if tot_g < 0.5 else ""))
        th["ws_box"] = ws_box
else:
    print(f"G3 THEATER: no *_r0N_*.manifest.json written in the last 10 min under {theater} (set THEATER_DIR=)")
# ---- per-card feeder WITHOUT early exit (legacy ladder, one launch per rung per period) ----
rungs = len(th) - (1 if "ws_box" in th else 0) or 6
for T in (15, 30, 60):
    lps = rungs / T; ovh = lps * ser; util = 1 - ovh if ovh < 1 else 0
    ws_card = util * peak / tw_leg
    print(f"G3 FEEDER, NO EARLY EXIT, period {T:2d}s: {lps:.2f} launches/s/card, init overhead {ovh:.0%} -> util {util:.0%} -> {ws_card:,.0f} w/s/card = {ws_card*gpus:,.0f} box (t/w {tw_leg}); rung-1 batch {ws_card*T*S:,.0f} cands {'>=' if ws_card*T*S >= knee else '<'} knee")
print(f"G3 AGGREGATED PIPELINE -- one feeder per card, mega-rings of K ks, waves of the UNCHANGED binary; t/w = (1/beta) x schedule overshoot; every wave >= knee; K3 = K for <=3 mega-rings in flight:")
print(f"G3 sizing rule: every wave >= knee ({knee:,}) AND kernel >= 9 x serialised launch cost ({ser*1000:.0f} ms) -> K; K3 = K for <=3 mega-rings in flight (cold {cold*1000:.0f} ms); wall x includes launch efficiency")
print(f"{'schedule':>18} {'waves':>5} {'t/w':>6} {'xtests':>6} {'K':>8} {'inflt':>5} {'K3':>8} {'RAM3 GB':>8} {'T3 s':>6} {'w/s card':>9} {'wall x':>6}")
rows = []
for name, b in schedules:
    waves = len(b) - 1; ov = Etests(b) / E1; tw = tw_ee1 * ov
    alive = [(1-beta)**b[w-1] for w in range(1, len(b))]; width = [b[w] - b[w-1] for w in range(1, len(b))]
    minwa = min(wd * al for wd, al in zip(width, alive))
    Kknee = knee / minwa                                   # every wave >= knee
    Kser = 9 * ser * peak / minwa                          # every wave's kernel >= 9x the serialised launch cost (<=10% launch overhead)
    K = int(math.ceil(max(Kknee, Kser) / 1000.0) * 1000)
    gpu_min = lambda K: min(K * wd * al / peak for wd, al in zip(width, alive))
    inflight = int(math.ceil(1 + cold / gpu_min(K)))
    K3 = K
    while 1 + cold / gpu_min(K3) > 3: K3 = int(K3 * 1.25)
    K3 = int(math.ceil(K3 / 1000.0) * 1000)
    ram3 = 3 * K3 * S * 256 / 1e9
    eff = 1 / (1 + ser / gpu_min(K3))                       # launch efficiency at the smallest wave (conservative)
    ws_gpu = peak * eff / tw; ws = min(ws_gpu, feed_max); gain = ws / min(app_leg, feed_max); T3 = K3 / ws
    rows.append(dict(name=name, waves=waves, tw=tw, xtests=tw_leg/tw, K=K, inflight=inflight, K3=K3, ram3=ram3, T3=T3, ws=ws, ws_gpu=ws_gpu, gain=gain, eff=eff))
    print(f"{name:>18} {waves:5d} {tw:6.1f} {tw_leg/tw:6.2f} {K:8d} {inflight:5d} {K3:8d} {ram3:8.1f} {T3:6.0f} {ws:9,.0f} {gain:6.2f}")
feas = [r for r in rows if r["ram3"] <= 0.5 * ram_gb]
best = max(feas or rows, key=lambda r: r["gain"])
simple = max([r for r in (feas or rows) if r["waves"] <= 6] or [best], key=lambda r: r["gain"])
fb = "GPU-bound" if feed_max >= best["ws_gpu"] else f"FEED-BOUND at {feed_max/best['ws_gpu']:.0%} -> wall gain capped x{best['gain']:.2f} (more loops/cores or cheaper make to lift)"
print(f"G3 FEED: best schedule wants {best['ws_gpu']:,.0f} w/s per card; make side offers {feed_max:,.0f} w/s max ({best['ws_gpu']/loop_ws:.0f} loops/card needed) -> {fb}")
print(f"G3 CHOICE (model): max gain = {best['name']}: {best['waves']} launches/mega-ring, t/w {best['tw']:.1f} (x{best['xtests']:.2f} tests), K>={best['K3']:,} ks = {best['K3']/ring_w:.0f} rings, <=3 in flight, {best['ram3']:.1f} GB, period {best['T3']:.0f} s, wall x{best['gain']:.2f}")
if simple is not best:
    print(f"G3 SIMPLER:  {simple['name']}: {simple['waves']} launches, t/w {simple['tw']:.1f} (x{simple['xtests']:.2f}), K>={simple['K3']:,} ks, {simple['ram3']:.1f} GB, period {simple['T3']:.0f} s, wall x{simple['gain']:.2f}  [decision is yours: S4]")
print("G3 BUILD IMPLIED: ee_serve = per-card feeder (loops drop rings into a queue dir; feeder concatenates K ks into a mega-ring, runs the waves with ee_drive's logic, writes each ring's v.bin + tested.json back atomically). No binary change; A+B semantics already certified on this box.")
json.dump(dict(cold_ms=cold*1000, knee=knee, peak=peak, lat_ms=lat*1000, S=S, ring_w=ring_w, loop_ws=loop_ws, tw_leg=tw_leg, tw_ee1=tw_ee1,
               feed_now=feed_now, feed_max=feed_max, app_leg=app_leg, loops_card=loops_card, cores=cores, gpus=gpus, ram_gb=ram_gb,
               rows=rows, choice=best["name"], simpler=simple["name"], gain=best["gain"]), open(outp, "w"), indent=1)
print(f"G3 wrote {outp}")
PYG
  local rc=${PIPESTATUS[0]}
  [ $rc -eq 0 ] && mark G3 "geometry=$P3/o1_geometry.json choice=\"$($PY -c "import json;d=json.load(open('$P3/o1_geometry.json'));print(d['choice'])")\" gain=$($PY -c "import json;print(round(json.load(open('$P3/o1_geometry.json'))['gain'],2))")" || return 1
}

# ------------------------------------------------------------------ drill
drill(){
  hr; say "== DRILL $(stamp) pattern='$DRILL_PATTERN'"
  local before; before=$(pgrep -fc "$DRILL_PATTERN")
  [ "$before" -ge 1 ] || { say "no process matches '$DRILL_PATTERN' (set DRILL_PATTERN=)"; return 1; }
  local victim; victim=$(pgrep -f "$DRILL_PATTERN" | head -1)
  say "alive=$before  victim pid=$victim  cmd: $(tr '\0' ' ' < /proc/$victim/cmdline | cut -c1-120)"
  read -r -p "kill -9 $victim and time the watchdog (<=10 min)?  type YES: " ans; [ "$ans" = "YES" ] || { say "drill aborted"; return 1; }
  local t0; t0=$(date +%s); kill -9 "$victim"; say "killed at $(stamp); polling every 20 s ..."
  while :; do
    sleep 20; local now; now=$(pgrep -fc "$DRILL_PATTERN"); local dt=$(( $(date +%s) - t0 ))
    say "  t+${dt}s alive=$now"
    [ "$now" -ge "$before" ] && { mark DRILL "restored_s=$dt before=$before victim=$victim"; return 0; }
    [ $dt -ge 900 ] && { say "DRILL RED: not restored in 15 min -- watchdog pair / wrapper pattern broken. Do not extend."; return 1; }
  done
}

# ------------------------------------------------------------------ main
cmd=${1:-all}
case "$cmd" in
  status) hr; say "state ($STATE):"; sed 's/^/  /' "$STATE" | tee -a "$LOG"; say "log tail ($LOG):"; tail -n 25 "$LOG" | sed 's/^/  /';;
  reset)  read -r -p "forget all gate state in $STATE? type YES: " a; [ "$a" = "YES" ] && : > "$STATE" && say "state cleared";;
  drill)  drill;;
  G0) run_gate G0 g0;; G1) run_gate G1 g1;; G2) run_gate G2 g2;; G3) run_gate G3 g3;;
  all)
    hr; say "#### o1_gates v1.5 $(stamp) runner=$(shortsha "$0") log=$LOG state=$STATE"
    run_gate G0 g0 && run_gate G1 g1 && run_gate G2 g2 && run_gate G3 g3 || exit 1
    hr; say "ALL GREEN: G0 G1 G2 G3. You are at S4 (geometry choice). Paste me: bash $0 status | tail -40"
    say "Next: S4 = choose the schedule from G3 -> ee_serve build -> shadow hour 1 card/1 bay; drill: bash $0 drill";;
  *) echo "usage: bash $0 [all|status|G0|G1|G2|G3|drill|reset]"; exit 2;;
esac
