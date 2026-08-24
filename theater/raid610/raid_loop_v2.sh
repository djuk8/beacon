#!/bin/bash
# raid_loop_v2.sh v2.4 (VENUE knob: crown = 8-rung ladder cap 45) v2.3.1 (engine by absolute path -- ../scanhunt_v0.py pointed into shm; v2.3 loops died at start) (shm ring cycle) v2.2 (Q env knob) -- identical to raid_loop.sh except the launch step: the ring
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
ARGS="--zd 1439 --swap 2 3 5 7 11 --kdig 13 --merit $MERIT --Q $Q \
 --deep-q 0 --deep-from-ring 99 --rings $RINGS --bits 2048 --seed $S --kblock 20000"
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
while true; do
  shm_wait
  $PY "$HOME/beacon/raid610/scanhunt_v0.py" make --round 1 $ARGS || exit 1
  B=$(ls -t sc_r01_*.bin | head -1)
  for R in 1 2 3 4 5 6 7; do
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
    if [ $R -ge 6 ]; then cp -p "$BB" "${BB%.bin}.manifest.json" "$HOME_DIR/" 2>/dev/null; fi   # salvage fossils persist
    $PY "$HOME/beacon/raid610/scanhunt_v0.py" fold --round $R --bin $BB $ARGS \
      || { echo "FOLD FAIL $BB -- block abandoned"; break; }
    rm -f "$BB" "${BB%.bin}.v.bin"
    if [ $R -le 5 ]; then rm -f "${BB%.bin}.manifest.json"; fi
    [ $R -lt 7 ] && $PY "$HOME/beacon/raid610/scanhunt_v0.py" make --round $((R+1)) $ARGS
  done
  $PY "$HOME/beacon/raid610/scanhunt_v0.py" finish $ARGS >> finish.log 2>&1
done
