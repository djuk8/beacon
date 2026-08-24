#!/bin/bash
# shadow_start.sh -- one-card shadow: feeder on card $C + loops SEEDS under raid_loop_v2. Watchdog stays OFF. (C, 2026-08-21)
set -uo pipefail
C=${C:-0}; SEEDS=${SEEDS:-"$(seq -s' ' $((101+C*30)) $((130+C*30)))"}; R=$HOME/beacon/raid610; P3=$HOME/beacon/p3; PY=/venv/main/bin/python3
export Q=${Q:-$(cat $R/Q.txt 2>/dev/null || echo 100000)}
EE=""; [ -x "$P3/g1_fermat_v3" ] && EE="--driver-ee $P3/g1_fermat_v3"
cp "$P3/o1_kit/raid_loop_v2.sh" "$R/" && cp "$P3/o1_kit/ee_serve.py" "$P3/" && chmod +x "$R/raid_loop_v2.sh" "$P3/ee_serve.py"
echo "installed: raid_loop_v2 $(sha256sum "$R/raid_loop_v2.sh" | cut -c1-12)  ee_serve $(sha256sum "$P3/ee_serve.py" | cut -c1-12)  driver $(sha256sum "$P3/g1_fermat_v2" | cut -c1-12)"
cd "$R" && mkdir -p "queue/c$C"
pgrep -f "ee_serve.py --queue $R/queue/c$C " >/dev/null || for w in $(seq ${R1N:-3}); do setsid nohup $PY "$P3/ee_serve.py" --queue "$R/queue/c$C" --gpu "$C" --driver "$P3/g1_fermat_v2" $EE --lanes r1 --kwin ${KWIN:-$(cat $R/KWIN.txt 2>/dev/null || echo 165000)} --tmax ${TMAX:-20} --workers 1 --verbose >> "$R/feeder_c$C.log" 2>&1 </dev/null & done
setsid nohup $PY "$P3/ee_serve.py" --queue "$R/queue/c$C" --gpu "$C" --driver "$P3/g1_fermat_v2" $EE --lanes hi --tmax-hi ${TMAXHI:-1.5} --workers 1 --verbose >> "$R/feeder_c$C.log" 2>&1 </dev/null &
for s in $SEEDS; do f="$R/hunt_s$s.log"; [ -f "$f" ] && echo "$s $(stat -c%s "$f")" || echo "$s 0"; done >> "$R/queue/c$C/log_offsets.txt"
sleep 2; for s in $SEEDS; do pgrep -f "raid_loop_v2.sh $s " >/dev/null || { setsid nohup ./raid_loop_v2.sh "$s" "$C" >> "hunt_s$s.log" 2>&1 </dev/null & sleep 1; }; done
echo "$(date -u +%FT%TZ) shadow card $C: feeder $(pgrep -fc "ee_serve.py --queue $R/queue/c$C ") loops $(pgrep -fc raid_loop_v2.sh)"; tail -2 "feeder_c$C.log"
