#!/bin/bash
# gate_serve.sh v1.3 (DRV_EE= runs the ladder on the v3 in-driver path; S6 wave-vs-in-driver identity; S7 rm-bins)
# gate_serve.sh v1.2 (real driver -> 2048-bit synthetics by default; abort on ring-build failure)
# gate_serve.sh v1.1 (v1.0 glob sc_r01_*.bin caught .v.bin -- the gl_*.bin lesson again; fixed)
# gate_serve.sh v1.0 -- feeder gates (C, 2026-08-21).  Runs anywhere with the
# stub driver (DRV=stub) or on box1 with the real one.  Nothing touches the
# live theater: own work dir, own queue, own lock.
#   S1 byte-identity: N synthetic rings through the queue vs legacy full runs
#   S2 loop fallback: no feeder -> submit_wait cancels and legacy-launches
#   S3 crash/resume: kill -9 the feeder mid-mega-ring, restart, all rings done
#   S4 fossils through the queue (FIXTURES='a.bin b.bin c.bin', real legacy v.bin)
#   S5 (SCANHUNT=path) N5 real 2048-bit rings from scanhunt make -> one mega-ring -> throughput + identity
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=${W:-/tmp/gate_serve}; LOG=$W/gate_serve.log; PY=${PY:-python3}
DRV=${DRV:-$HERE/gate_o1_stubs/stub_driver.py}; GPU=${GPU:-0}
if [[ "$DRV" == *stub_driver* ]]; then BITS=${BITS:-512}; N=${N:-12}; KS=${KS:-300}; S=${S:-97}
else BITS=${BITS:-2048}; N=${N:-6}; KS=${KS:-100}; S=${S:-60}; fi     # real driver: production bit class; small rings (2048-bit primes cost ~0.3 s each to plant)
CHUNK=${CHUNK:-6}; GROWTH=${GROWTH:-1.15}
KWIN=${KWIN:-1500}; TMAX=${TMAX:-3}; LOCK=$W/gpu.lock; Q=$W/queue
rm -rf "$W"; mkdir -p "$W" "$Q"; say(){ echo "$@" | tee -a "$LOG"; }
say "==== gate_serve v1.3 $(date -u +%FT%TZ) driver=$DRV driver_ee=${DRV_EE:-none} bits=$BITS rings=$N x $KS x $S chunk=$CHUNK growth=$GROWTH kwin=$KWIN"
EEOPT=""; [ -n "${DRV_EE:-}" ] && EEOPT="--driver-ee $DRV_EE"
feeder(){ $PY "$HERE/ee_serve.py" --queue "$Q" --gpu "$GPU" --driver "$DRV" $EEOPT --rm-bins 0 --kwin "$KWIN" --tmax "$TMAX" --chunk "$CHUNK" --growth "$GROWTH" --workers 2 --lock "$LOCK" --verbose >> "$W/feeder.log" 2>&1 & echo $!; }
feeder_wave(){ $PY "$HERE/ee_serve.py" --queue "$Q" --gpu "$GPU" --driver "$DRV" --rm-bins 0 --kwin "$KWIN" --tmax "$TMAX" --chunk "$CHUNK" --growth "$GROWTH" --workers 1 --lock "$LOCK" --verbose >> "$W/feeder.log" 2>&1 & echo $!; }
submit(){ # $1 stem  -> request
  printf '{"bin":"%s","out":"%s","seed":%s,"round":1,"bid":"%s"}\n' "$1.bin" "$1.v.bin" "$2" "${1##*_}" > "$Q/req/$(basename "$1")_$2.json.part"; mv "$Q/req/$(basename "$1")_$2.json.part" "$Q/req/$(basename "$1")_$2.json"; }
waitall(){ # $1 dir of stems  $2 timeout s
  local t=0; while [ $t -lt "$2" ]; do local miss=0; for b in "$1"/sc_r01_[0-9][0-9][0-9][0-9].bin; do [ -s "${b%.bin}.v.bin" ] || miss=$((miss+1)); done; [ $miss -eq 0 ] && return 0; sleep 1; t=$((t+1)); done; return 1; }
compare_dir(){ local ok=0 bad=0; for b in "$1"/sc_r01_[0-9][0-9][0-9][0-9].bin; do $PY "$HERE/compare_vbin.py" "${b%.bin}" "$CHUNK" "$GROWTH" >> "$LOG" 2>&1 && ok=$((ok+1)) || bad=$((bad+1)); done; say "  compared: $ok PASS $bad FAIL"; [ $bad -eq 0 ]; }

# ---------- S1
say "--- S1 byte-identity through the queue ($N rings, 3 hunt dirs) ---"
mkdir -p "$Q/req"; for h in 101 102 103; do $PY "$HERE/mkrings.py" "$W/hunt_s$h" --n $((N/3)) --ks $KS --S $S --bits $BITS --bid0 $((1000+h)) --seed $h --driver "$DRV" > /dev/null || { say "S1: mkrings/legacy driver failed (bits=$BITS?) -- abort"; exit 1; }; done
FP=$(feeder); sleep 1
for h in 101 102 103; do for b in "$W/hunt_s$h"/sc_r01_[0-9][0-9][0-9][0-9].bin; do submit "${b%.bin}" $h; done; done
waitall "$W/hunt_s101" 600 && waitall "$W/hunt_s102" 600 && waitall "$W/hunt_s103" 600 && say "  all verdict files present" || say "  S1 FAIL: timeout waiting for verdicts"
ok1=1; for h in 101 102 103; do compare_dir "$W/hunt_s$h" || ok1=0; done
say "  ledger lines: $(wc -l < "$Q/ledger.jsonl" 2>/dev/null || echo 0)  done: $(ls "$Q/done" | wc -l)  failed: $(ls "$Q/failed" 2>/dev/null | wc -l)  claimed-left: $(ls "$Q/claimed" | wc -l)"
grep -E "rings,.*launches" "$W/feeder.log" | tail -3 | sed 's/^/  /' | tee -a "$LOG"
kill "$FP" 2>/dev/null; wait "$FP" 2>/dev/null
[ $ok1 -eq 1 ] && [ "$(ls "$Q/done" | wc -l)" -eq "$N" ] && say "S1: PASS" || { say "S1: FAIL"; exit 1; }

# ---------- S2 loop fallback (no feeder)
say "--- S2 loop fallback: no feeder, submit_wait must cancel and legacy-launch ---"
rm -rf "$Q"; mkdir -p "$Q/req"; $PY "$HERE/mkrings.py" "$W/fb" --n 1 --ks 50 --S 40 --bits $BITS --bid0 2000 --driver "$DRV" >/dev/null || { say "S2: mkrings failed -- abort"; exit 1; }
( cd "$W/fb" && S=101 C=$GPU R=1 Q="$Q" WAIT1=2 WAIT2=4 DRV="$DRV" && eval "$(sed -n '/^submit_wait()/,/^}/p' "$HERE/raid_loop_v2.sh")" && mkdir -p "$Q/cancelled" \
  && { t0=$(date +%s); if submit_wait sc_r01_2000.bin sc_r01_2000.v.bin; then echo "unexpected: verdict without feeder"; exit 1; fi; echo "  cancelled after $(( $(date +%s) - t0 )) s (expect ~2); cancelled: $(ls "$Q/cancelled" | wc -l)"; CUDA_VISIBLE_DEVICES=$C flock "$LOCK" "$DRV" sc_r01_2000.bin sc_r01_2000.v.bin && cmp -s sc_r01_2000.v.bin sc_r01_2000.legacy.v.bin && echo "  legacy launch produced identical verdicts"; } ) 2>&1 | tee -a "$LOG" | grep -q "identical" && say "S2: PASS" || { say "S2: FAIL"; exit 1; }

# ---------- S3 crash mid-mega-ring, resume
say "--- S3 crash/resume ---"
rm -rf "$Q"; mkdir -p "$Q/req"; $PY "$HERE/mkrings.py" "$W/cr" --n 6 --ks $KS --S $S --bits $BITS --bid0 3000 --driver "$DRV" >/dev/null || { say "S3: mkrings failed -- abort"; exit 1; }
FP=$(feeder); sleep 0.5; for b in "$W/cr"/sc_r01_[0-9][0-9][0-9][0-9].bin; do submit "${b%.bin}" 101; done
sleep $((TMAX+1)); kill -9 "$FP"; sleep 0.5
say "  after kill -9: claimed=$(ls "$Q/claimed" | wc -l) done=$(ls "$Q/done" 2>/dev/null | wc -l) req=$(ls "$Q/req" | wc -l) shm-leftovers=$(ls -d /dev/shm/ees_* 2>/dev/null | wc -l)"
rm -rf /dev/shm/ees_* 2>/dev/null
FP=$(feeder); waitall "$W/cr" 600 && say "  all 6 verdicts present after restart" || say "  S3 FAIL: timeout"
compare_dir "$W/cr" && [ "$(ls "$Q/done" | wc -l)" -eq 6 ] && say "S3: PASS" || { say "S3: FAIL"; kill "$FP"; exit 1; }
kill "$FP" 2>/dev/null; wait "$FP" 2>/dev/null


# ---------- S6 (DRV_EE set): wave path vs in-driver path on the same rings -> byte-identical; S7: --rm-bins 1 removes the bin
if [ -n "${DRV_EE:-}" ]; then
  say "--- S6 wave-mode (v2) vs in-driver (v3) on the S1 rings ---"
  rm -rf "$Q"; mkdir -p "$Q/req"; FP=$(feeder_wave); sleep 0.5
  for h in 101 102 103; do for b in "$W/hunt_s$h"/sc_r01_[0-9][0-9][0-9][0-9].bin; do mv "${b%.bin}.v.bin" "${b%.bin}.ee.v.bin"; submit "${b%.bin}" $h; done; done
  waitall "$W/hunt_s101" 900 && waitall "$W/hunt_s102" 900 && waitall "$W/hunt_s103" 900 || say "  S6: timeout"
  bad=0; for h in 101 102 103; do for b in "$W/hunt_s$h"/sc_r01_[0-9][0-9][0-9][0-9].bin; do cmp -s "${b%.bin}.v.bin" "${b%.bin}.ee.v.bin" || bad=$((bad+1)); done; done
  kill "$FP" 2>/dev/null; wait "$FP" 2>/dev/null
  [ $bad -eq 0 ] && say "S6: PASS (all S1 rings identical between v2 wave path and v3 in-driver path)" || { say "S6: FAIL ($bad differ)"; exit 1; }
  say "--- S7 --rm-bins 1 ---"
  rm -rf "$Q"; mkdir -p "$Q/req"; $PY "$HERE/mkrings.py" "$W/rm" --n 1 --ks 20 --S 20 --bits $BITS --bid0 4000 --driver "$DRV" >/dev/null || { say "S7: mkrings failed"; exit 1; }
  FP=$($PY "$HERE/ee_serve.py" --queue "$Q" --gpu "$GPU" --driver "$DRV" $EEOPT --rm-bins 1 --kwin 1 --tmax 1 --workers 1 --lock "$LOCK" --once >> "$W/feeder.log" 2>&1 & echo $!); sleep 0.5
  submit "$W/rm/sc_r01_4000" 101; t=0; while [ $t -lt 300 ] && [ ! -s "$W/rm/sc_r01_4000.v.bin" ]; do sleep 1; t=$((t+1)); done; sleep 1
  [ -s "$W/rm/sc_r01_4000.v.bin" ] && [ ! -f "$W/rm/sc_r01_4000.bin" ] && say "S7: PASS (verdict present, candidate bin removed)" || { say "S7: FAIL"; exit 1; }
fi
# ---------- S4 fossils (box1)
if [ -n "${FIXTURES:-}" ]; then
  say "--- S4 fossil trios through the queue (real legacy v.bin) ---"
  rm -rf "$Q"; mkdir -p "$Q/req" "$W/fx"; i=0
  for f in $FIXTURES; do i=$((i+1)); s="$W/fx/sc_r01_$(printf %04d $i)"; ln -s "$f" "$s.bin"; ln -s "${f%.bin}.manifest.json" "$s.manifest.json"; ln -s "${f%.bin}.v.bin" "$s.legacy.v.bin"; done
  FP=$(feeder); sleep 0.5; for b in "$W/fx"/sc_r01_[0-9][0-9][0-9][0-9].bin; do submit "${b%.bin}" 999; done
  waitall "$W/fx" 3600 && say "  verdicts present" || say "  S4 FAIL: timeout"
  compare_dir "$W/fx" && say "S4: PASS" || { say "S4: FAIL"; kill "$FP"; exit 1; }
  grep -E "rings,.*launches" "$W/feeder.log" | tail -3 | sed 's/^/  /' | tee -a "$LOG"
  kill "$FP" 2>/dev/null; wait "$FP" 2>/dev/null
fi

# ---------- S5 production-geometry throughput (box1): real 2048-bit rings from scanhunt make, one card
if [ -n "${SCANHUNT:-}" ]; then
  N5=${N5:-40}; say "--- S5 throughput: $N5 real rings via scanhunt make (parallel), 3 legacy launches for identity, one mega-ring through the feeder ---"
  rm -rf "$Q"; mkdir -p "$Q/req" "$W/mk"
  RINGS=1568,4374,7244,10198,13500,17734,26542
  MARGS="--zd 1439 --swap 2 3 5 7 11 --kdig 13 --merit 37.8241 --Q 100000 --deep-q 0 --deep-from-ring 99 --rings $RINGS --bits 2048 --kblock 20000"
  t0=$(date +%s); for s5 in $(seq 9001 $((9000+N5))); do ( mkdir -p "$W/mk/hunt_s$s5" && cd "$W/mk/hunt_s$s5" && $PY "$SCANHUNT" make --round 1 $MARGS --seed $s5 >make.log 2>&1 ) & done; wait
  say "  made $(ls "$W/mk"/hunt_s*/sc_r01_[0-9][0-9][0-9][0-9].bin 2>/dev/null | wc -l) rings in $(( $(date +%s) - t0 )) s"
  i=0; tl=0; for b in $(ls "$W/mk"/hunt_s*/sc_r01_[0-9][0-9][0-9][0-9].bin | head -3); do t1=$(date +%s.%N); CUDA_VISIBLE_DEVICES=$GPU "$DRV" "$b" "${b%.bin}.legacy.v.bin" 2>/dev/null; tl=$(echo "$tl + $(date +%s.%N) - $t1" | bc); i=$((i+1)); done
  say "  legacy: 3 full launches in ${tl}s -> $(echo "scale=1; $tl/3" | bc) s/ring incl. cold start"
  FP=$($PY "$HERE/ee_serve.py" --queue "$Q" --gpu "$GPU" --driver "$DRV" $EEOPT --rm-bins 0 --kwin ${KWIN5:-330000} --tmax 5 --chunk "$CHUNK" --growth "$GROWTH" --workers 1 --lock "$LOCK" --verbose >> "$W/feeder.log" 2>&1 & echo $!); sleep 0.5
  t2=$(date +%s); for b in "$W/mk"/hunt_s*/sc_r01_[0-9][0-9][0-9][0-9].bin; do submit "${b%.bin}" $(basename "$(dirname "$b")" | tr -dc 0-9); done
  t=0; while [ $t -lt 1800 ]; do miss=0; for b in "$W/mk"/hunt_s*/sc_r01_[0-9][0-9][0-9][0-9].bin; do [ -s "${b%.bin}.v.bin" ] || miss=$((miss+1)); done; [ $miss -eq 0 ] && break; sleep 1; t=$((t+1)); done
  say "  feeder: all $N5 rings back in $(( $(date +%s) - t2 )) s wall (submit -> last verdict); legacy would be ~$(echo "scale=0; $tl*$N5/3" | bc) s for the same rings at rung 1 alone"
  grep -E "wave|rings,.*launches" "$W/feeder.log" | tail -8 | sed 's/^/  /' | tee -a "$LOG"
  ok5=1; for b in $(ls "$W/mk"/hunt_s*/sc_r01_[0-9][0-9][0-9][0-9].bin | head -3); do $PY "$HERE/compare_vbin.py" "${b%.bin}" "$CHUNK" "$GROWTH" >> "$LOG" 2>&1 || ok5=0; done
  kill "$FP" 2>/dev/null; wait "$FP" 2>/dev/null
  [ $ok5 -eq 1 ] && say "S5: PASS (identity on 3 rings; throughput lines above are the design-point measurement)" || { say "S5: FAIL (identity)"; exit 1; }
fi
say "==== gate_serve: ALL PASS ($([ -n "${FIXTURES:-}" ] && echo S1-S4 || echo 'S1-S3; S4 needs FIXTURES= on box1'))"
