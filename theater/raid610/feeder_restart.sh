#!/bin/bash
# feeder_restart.sh -- graceful feeder swap on card $C: TERM (finishes the mega-ring in flight), wait, start the kit copy. Loops keep running (they wait up to 120 s, then fall back).
C=${C:-0}; R=$HOME/beacon/raid610; P3=$HOME/beacon/p3; PY=/venv/main/bin/python3
EE=""; [ -x "$P3/g1_fermat_v3" ] && EE="--driver-ee $P3/g1_fermat_v3"
cp "$P3/o1_kit/ee_serve.py" "$P3/ee_serve.py" && echo "ee_serve $(sha256sum "$P3/ee_serve.py" | cut -c1-12)"
pkill -TERM -f "ee_serve.py --queue $R/queue/c$C " ; for i in $(seq 600); do pgrep -f "ee_serve.py --queue $R/queue/c$C " >/dev/null || break; sleep 1; done; pkill -9 -f "ee_serve.py --queue $R/queue/c$C " 2>/dev/null
sleep 1; echo "old feeders gone after ${i}s (left: $(pgrep -fc "ee_serve.py --queue $R/queue/c$C ")); claimed left: $(ls $R/queue/c$C/claimed | wc -l) (re-queued by the new one)"
cd "$R" && for w in $(seq ${R1N:-3}); do setsid nohup $PY "$P3/ee_serve.py" --queue "$R/queue/c$C" --gpu "$C" --driver "$P3/g1_fermat_v2" $EE --lanes r1 --kwin ${KWIN:-$(cat $R/KWIN.txt 2>/dev/null || echo 165000)} --tmax ${TMAX:-20} --workers 1 --verbose >> "$R/feeder_c$C.log" 2>&1 </dev/null & done
setsid nohup $PY "$P3/ee_serve.py" --queue "$R/queue/c$C" --gpu "$C" --driver "$P3/g1_fermat_v2" $EE --lanes hi --tmax-hi ${TMAXHI:-1.5} --workers 1 --verbose >> "$R/feeder_c$C.log" 2>&1 </dev/null &
sleep 2; echo "new feeder: $(pgrep -fc "ee_serve.py --queue $R/queue/c$C ")  loops: $(pgrep -fc raid_loop_v2.sh)"; tail -2 "$R/feeder_c$C.log"
