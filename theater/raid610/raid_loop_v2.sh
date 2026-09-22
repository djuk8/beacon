#!/bin/bash
# raid_loop_v2.sh v2.19 (unique fossil names) v2.18 (BSD=3 consumer) v2.17 (wait-when-daemons) v2.16 (any-queue claim) v2.15 (claim backoff) v2.14 (claim fix) v2.13 (consume-or-make) v2.12 (BSD consumer mode) v2.11 (DEEPR knob) v2.10 (SELECT knob) v2.9 (manifest-only fossil copy) v2.8 (MAKESLOTS token: cap concurrent makes) v2.7 (make/fold at nice 10: GPU host path keeps its cores) v2.6 (O3 deep knobs: DEEPQ/DFR) v2.5 (rung count from venue edges; fossil copy loud) v2.4 (VENUE knob: crown = 8-rung ladder cap 45) v2.3.1 (engine by absolute path -- ../scanhunt_v0.py pointed into shm; v2.3 loops died at start) (shm ring cycle) v2.2 (Q env knob) -- identical to raid_loop.sh except the launch step: the ring
# is SUBMITTED to the card's feeder (ee_serve) and the loop waits for the
# verdict file; if the feeder is absent/slow the request is cancelled (atomic
# rename; only possible while unclaimed) and the legacy launch runs.  make,
# fold, finish, rm: unchanged.  (C, 2026-08-21)
S=$1; C=$2
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
VENUE=${VENUE:-$(cat $HOME/beacon/raid610/VENUE.txt 2>/dev/null || echo raid610)}
if [ "$VENUE" = crown ]; then
  RINGS=1568,4374,7244,10198,13500,17734,22818,31576; MERIT=45.0     # G-L1 2026-08-23, ladder_crown.json, cap 45
else
  RINGS=1568,4374,7244,10198,13500,17734,26542; MERIT=37.8241
fi
Q=${Q:-100000}   # sieve depth; E is Q-invariant. (NOTE: $Q is reused as the queue dir below -- ARGS consumes this first; do not reorder.)
DEEPQ=$(cat $HOME/beacon/raid610/DEEPQ.txt 2>/dev/null || echo ${DEEPQ:-0})   # O3 tier-1.5: 100000000 = solve-deepen r1 to 1e8 (M1D-gated)
DFR=${DFR:-1}
DEEPR=$(cat $HOME/beacon/raid610/DEEPR.txt 2>/dev/null || echo ${DEEPR:-1})   # deepen rungs 1..DEEPR
SELECT=$(cat $HOME/beacon/raid610/SELECT.txt 2>/dev/null || echo ${SELECT:-1})   # sparse-window selection: sieve N*kblock, keep sparsest 1/N (SELECT_PREREG)
ARGS="--zd 1439 --swap 2 3 5 7 11 --kdig 13 --merit $MERIT --Q $Q \
 --deep-q $DEEPQ --deep-from-ring $DFR --deep-rings $DEEPR --select $SELECT --rings $RINGS --bits 2048 --seed $S --kblock 20000"
PY=${PY:-/venv/main/bin/python3}; DRV=${DRV:-$HOME/beacon/p3/g1_fermat_v2}
Q=${QUEUE:-$HOME/beacon/raid610/queue/c$C}; WAIT1=${WAIT1:-120}; WAIT2=${WAIT2:-1800}
mkdir -p "$Q/req" "$Q/cancelled"
submit_wait(){  # $1 bin (in cwd)  $2 out v.bin ; 0 = verdict file present
  local bb out name req t=0
  bb=$(readlink -f "$1"); out=$(dirname "$bb")/$(basename "$2"); name="s${S}_r${R}_$(basename "${bb%.bin}")_$$"; req="$Q/req/$name.json"
  printf '{"bin":"%s","out":"%s","seed":%s,"round":%s,"bid":"%s"}\n' "$bb" "$out" "$S" "$R" "${bb##*_}" > "$req.part" && mv "$req.part" "$req"
  # v2.1: cancel ONLY if no feeder process exists for this queue (a slow feeder is waited for; cancelling into
  # legacy launches under the same lock starves the feeder -- the 2026-08-21 convoy).  Hard cap WAIT2 on claimed.
  while [ $t -lt $((WAIT2*2)) ]; do
    [ -s "$out" ] && return 0
    [ -f "$Q/failed/$name.json" ] && { echo "FEEDER FAILED $bb"; return 1; }
    if [ $((t % 40)) -eq 39 ] && ! pgrep -f "ee_serve.py --queue $Q " >/dev/null; then
      if mv "$req" "$Q/cancelled/$name.json" 2>/dev/null; then echo "FEEDER ABSENT $bb -- cancelled, legacy launch"; return 1; fi
    fi
    sleep 0.5; t=$((t+1))
  done
  if mv "$req" "$Q/cancelled/$name.json" 2>/dev/null; then echo "FEEDER NEVER CLAIMED $bb in ${WAIT2}s -- cancelled, legacy launch"; return 1; fi
  echo "FEEDER STUCK $bb"; return 1
}
# v2.3: the ring cycle runs in /dev/shm (the overlay disk was the four-wide bottleneck: ~500 MB/s of bins).
# Persistent: sc_state.json + finish.log symlinked to the overlay hunt dir; rung>=6 bins+manifests copied there
# after the drive (salvage fossils); shared pre-warmed residue cache; 20 GB shm watermark instead of ENOSPC death.
HOME_DIR=$HOME/beacon/raid610/hunt_s$S; WORK=${WORK_BASE:-/dev/shm/beacon}/hunt_s$S
mkdir -p "$HOME_DIR" "$WORK"
ln -sf "$HOME_DIR/sc_state.json" "$WORK/sc_state.json"; ln -sf "$HOME_DIR/finish.log" "$WORK/finish.log"
ln -sfn "$HOME/beacon/raid610/.sc_cache" "$WORK/.sc_cache"
cd "$WORK"
shm_wait(){ while [ "$(df -m /dev/shm | awk 'NR==2{print $4}')" -lt ${SHM_MIN_MB:-20480} ]; do echo "SHM LOW -- waiting"; sleep 30; done; }
MAKESLOTS=${MAKESLOTS:-$(cat $HOME/beacon/raid610/MAKESLOTS.txt 2>/dev/null || echo 56)}   # box-wide cap on concurrent makes (herd contention caps GPU serving: 230k -> 421k t/s when quiet, measured 2026-09-02)
TOK=$HOME/beacon/raid610/.makeslots; mkdir -p "$TOK"
slot_take(){ local s; for s in $(shuf -i 1-$MAKESLOTS); do exec 9>"$TOK/slot$s"; flock -n 9 && return 0; exec 9>&-; done
             s=$(( (RANDOM % MAKESLOTS) + 1 )); exec 9>"$TOK/slot$s"; flock 9; }          # all busy: block on a random slot
slot_free(){ exec 9>&- 2>/dev/null; }
while true; do
  shm_wait
  BSD=$(cat $HOME/beacon/raid610/BSD.txt 2>/dev/null || echo 0)
  if [ "$BSD" = 1 ] || [ "$BSD" = 2 ] || [ "$BSD" = 3 ]; then       # v2.12 CONSUMER MODE (BSD=3: sieve card, v2.18): adopt a ready ring from the card's sieve daemon
    READY=$HOME/beacon/raid610/ready/c$C; rm -f sc_r0*.bin sc_r0*.manifest.json sc_carry_r*.json sc_r0*.v.bin
    NDAEM=$(cat $HOME/beacon/raid610/BSDN_EFF.txt 2>/dev/null || echo 0)
    if [ "$NDAEM" -gt 0 ]; then W8=${BSDWAIT:-100000}; else W8=${BSDWAIT:-30}; fi   # v2.17: boxes WITH daemons WAIT (a fallback storm starves the GPU path); fallback only where no daemon exists
    GOT=0; EMPTY=0
    while [ $EMPTY -lt $W8 ]; do
      F=$(ls $READY/sc_r01_*.manifest.json 2>/dev/null | shuf -n 1)
      [ -z "$F" ] && F=$(ls $HOME/beacon/raid610/ready/c*/sc_r01_*.manifest.json 2>/dev/null | shuf -n 1)   # v2.16: own queue first, then ANY card's (rings are card-agnostic; balances supply)
      [ -z "$F" ] && { sleep 1; EMPTY=$((EMPTY+1)); continue; }
      RD=$(dirname "$F"); N=$(basename "$F" .manifest.json)
      mv "$RD/$N.manifest.json" ./ 2>/dev/null || { sleep 0.$((RANDOM % 4 + 1)); continue; }   # lost race: back off 0.1-0.4 s (v2.15)
      mv "$RD/$N.bin" ./ 2>/dev/null || { echo "$(date -u) BSD: bin missing for $N"; rm -f "$N.manifest.json"; continue; }
      GOT=1; break
    done
    if [ $GOT = 0 ]; then echo 1 >> $HOME/beacon/raid610/fallback_c$C.log; slot_take; nice -n 10 $PY "$HOME/beacon/raid610/scanhunt_v0.py" make --round 1 ${ARGS/--select $SELECT/--select 1} || exit 1; slot_free; fi   # fallback make is a cheap 1x make
  else
    slot_take; nice -n 10 $PY "$HOME/beacon/raid610/scanhunt_v0.py" make --round 1 $ARGS || exit 1
    slot_free
  fi
  B=$(ls -t sc_r01_*.bin | head -1)
  NR=$(echo "$RINGS" | awk -F, '{print NF}')   # rungs follow the venue's edge list (8 crown, 7 raid610) -- the hardcoded 7 was the rung-8 hole, 2026-08-24
  for R in $(seq 1 $NR); do
    BB=${B/r01/r0$R}
    [ -f "$BB" ] || break
    ok=0
    for try in 1 2 3; do
      if submit_wait "$BB" "${BB%.bin}.v.bin"; then ok=1; break; fi
      CUDA_VISIBLE_DEVICES=$C flock /tmp/raidgpu$C.lock \
        "$DRV" $BB ${BB%.bin}.v.bin \
        && [ -s "${BB%.bin}.v.bin" ] && { ok=1; break; }
      echo "DRIVE RETRY $try $BB"; sleep $((try*5))
    done
    [ $ok = 1 ] || { echo "DRIVE FAIL $BB -- block abandoned"; \
      rm -f "$BB" "${BB%.bin}.v.bin"; break; }
    if [ $R -ge 6 ]; then M="${BB%.bin}.manifest.json"; cp -p "$M" "$HOME_DIR/$(basename "${M%.manifest.json}")_$(date +%s%N).manifest.json" || echo "FOSSIL COPY FAIL r$R $M"; fi   # manifests only: salvage recomputes from k; bins were the disk eater
    nice -n 10 $PY "$HOME/beacon/raid610/scanhunt_v0.py" fold --round $R --bin $BB $ARGS \
      || { echo "FOLD FAIL $BB -- block abandoned"; break; }
    rm -f "$BB" "${BB%.bin}.v.bin"
    if [ $R -le 5 ]; then rm -f "${BB%.bin}.manifest.json"; fi
    if [ $R -lt $NR ]; then   # v2.8: was hardcoded 7 -> round 8 was never MADE (rung-8 hole, second half; ledger showed zero round-8 for 4.5 days)
      slot_take; nice -n 10 $PY "$HOME/beacon/raid610/scanhunt_v0.py" make --round $((R+1)) $ARGS; slot_free
    fi
  done
  $PY "$HOME/beacon/raid610/scanhunt_v0.py" finish $ARGS >> finish.log 2>&1
done
