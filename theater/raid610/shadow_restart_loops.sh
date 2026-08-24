#!/bin/bash
# shadow_restart_loops.sh -- restart the shadow loops on card $C under the current kit loop script. Kills the loops
# (their in-flight ring is abandoned), lets children finish, restarts the feeders, age-gated cleanup of orphaned
# in-flight ring files (-mmin +30: never a live make), then starts the loops again. Watchdog stays off.
set -uo pipefail
C=${C:-0}; R=$HOME/beacon/raid610; P3=$HOME/beacon/p3
SEEDS=${SEEDS:-"$(pgrep -fa raid_loop_v2.sh | grep -oE 'raid_loop_v2.sh [0-9]+ '"$C"'\b' | awk '{print $2}' | sort -n | tr '\n' ' ')"}
[ -n "$SEEDS" ] || SEEDS="$(seq -s' ' $((101+C*30)) $((130+C*30)))"
echo "seeds: $SEEDS"
pkill -f "raid_loop_v2.sh [0-9]+ $C\b"; sleep 3; echo "loops left: $(pgrep -fc raid_loop_v2.sh)"
bash "$P3/o1_kit/feeder_restart.sh"
rm -f "$R/queue/c$C"/req/*.json "$R/queue/c$C"/claimed/*.json 2>/dev/null          # requests of dead loops
find "$R"/hunt_s*/ -maxdepth 1 \( -name 'sc_r0[1-7]_[0-9]*.bin' -o -name 'sc_r0[1-7]_[0-9]*.v.bin' -o -name 'sc_r0[1-7]_[0-9]*.v.bin.part' \) -mmin +30 -delete 2>/dev/null
C=$C SEEDS="$SEEDS" bash "$P3/o1_kit/shadow_start.sh"
