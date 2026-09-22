#!/bin/bash
# gate_ladder.sh -- REPLAY GATE: the shell loop (raid_loop_v2.sh) and the ladder manager (ladder.py) process the SAME two rung-1 rings
# with the SAME stub feeder (true primality => deterministic verdicts). PASS = identical per-round advance counts, finish output, served requests.
set -u; export HOME=/home/claude; R=$HOME/beacon/raid610; KIT=${KIT:-/home/claude/o1_kit}; SRC=${SRC:-/home/claude/g3a}; PY=python3; S=9301
kill_strays(){ pkill -f "[e]e_serve.py --queue /home/claude"; pkill -f "[l]adder.py --card 0"; pkill -f "[r]aid_loop_v2.sh 9301"; sleep 1; }
kill_strays; rm -rf $R /tmp/lgwork /tmp/lgbank; mkdir -p $R/queue/c0/req $R/ready/c0 /tmp/lgwork /tmp/lgbank/mk
cp /home/claude/ladder/ladder.py $SRC/scanhunt_v0.py $SRC/fastmake.py $SRC/fastmake_numpy.py $SRC/deep_primes.py $SRC/resonance_map.py $SRC/*.so $R/ 2>/dev/null
cp $KIT/raid_loop_v2.sh $KIT/ee_serve.py $KIT/ee_drive.py $R/; cp -r $KIT/gate_o1_stubs $R/; mkdir -p $SRC/.sc_cache; ln -sfn $SRC/.sc_cache $R/.sc_cache
echo crown > $R/VENUE.txt; echo 1 > $R/BSD.txt; echo 1 > $R/BSDN_EFF.txt; echo 1 > $R/SELECT.txt; echo 0 > $R/DEEPQ.txt; echo 1 > $R/DEEPR.txt; echo 8 > $R/MAKESLOTS.txt
ARGS="--zd 1439 --swap 2 3 5 7 11 --kdig 13 --merit 45.0 --Q 100000 --deep-q 0 --deep-from-ring 1 --deep-rings 1 --select 1 --rings 1568,4374,7244,10198,13500,17734,22818,31576 --bits 2048 --seed $S --kblock ${KB:-300}"
(cd /tmp/lgbank/mk && ln -sfn $SRC/.sc_cache .sc_cache && $PY $R/scanhunt_v0.py make --round 1 $ARGS >/dev/null 2>&1 && $PY $R/scanhunt_v0.py make --round 1 $ARGS >/dev/null 2>&1) || { echo "ring bank FAIL"; exit 2; }
ls /tmp/lgbank/mk/sc_r01_0001.bin /tmp/lgbank/mk/sc_r01_0002.bin >/dev/null 2>&1 || { echo "ring bank FAIL (no bins)"; exit 2; }
echo "bank: 2 rings"
feeder(){ $PY $R/ee_serve.py --queue $R/queue/c0 --gpu 0 --driver $R/gate_o1_stubs/stub_driver.py --rm-bins 0 --kwin 400 --tmax 2 --chunk 6 --growth 1.15 --workers 1 > $R/feeder_c0.log 2>&1 & echo $!; }
load_bank(){ cp /tmp/lgbank/mk/sc_r01_000[12].bin /tmp/lgbank/mk/sc_r01_000[12].manifest.json $R/ready/c0/; }
finish_lines(){ cat $R/hunt_s$S/finish.log 2>/dev/null | wc -l; }
wait_idle(){ # $1 timeout: finish.log has >= 2 lines and no ring files remain in the work dir for two consecutive checks
  local t=0 idle=0 n r
  while [ $t -lt $1 ]; do n=$(finish_lines); r=$(ls /tmp/lgwork/hunt_s$S/sc_r0* 2>/dev/null | wc -l)
    if [ "$n" -ge 2 ] && [ "$r" -eq 0 ]; then idle=$((idle+1)); [ $idle -ge 2 ] && return 0; else idle=0; fi
    sleep 3; t=$((t+3)); done; return 1; }
reset_venue(){ rm -rf $R/hunt_s$S /tmp/lgwork/hunt_s$S $R/queue/c0/done $R/queue/c0/claimed $R/queue/c0/failed $R/queue/c0/req/*; mkdir -p $R/queue/c0/req; }
# ---- run A: the shell loop ----
reset_venue; FP=$(feeder); sleep 2; load_bank
(cd $R && SHM_MIN_MB=0 WORK_BASE=/tmp/lgwork PY=$PY DRV=$R/gate_o1_stubs/stub_driver.py setsid nohup bash $R/raid_loop_v2.sh $S 0 > $R/hunt_A.log 2>&1 < /dev/null &)
wait_idle ${TMO:-900} && echo "run A (shell loop): done" || echo "run A: TIMEOUT"
kill_strays; kill $FP 2>/dev/null; sleep 1
cp $R/hunt_s$S/finish.log $R/finish_A.log; DONE_A=$(ls $R/queue/c0/done 2>/dev/null | wc -l); grep -aoE "round [0-9]+: [0-9]+ ks -> [0-9]+ advance" $R/hunt_A.log | sort > /tmp/lg_A.txt
# ---- run B: the ladder manager ----
reset_venue; rm -f $R/hunt_s$S.log; FP=$(feeder); sleep 2; load_bank
(cd $R && setsid nohup $PY $R/ladder.py --card 0 --seeds $S --workers 2 --shm-min-gb 0 --kitdir $R --work-base /tmp/lgwork --bsd 1 --venue crown > $R/ladder_c0.log 2>&1 < /dev/null &)
wait_idle ${TMO:-900} && echo "run B (ladder manager): done" || echo "run B: TIMEOUT"
kill_strays; kill $FP 2>/dev/null; sleep 1
cp $R/hunt_s$S/finish.log $R/finish_B.log; DONE_B=$(ls $R/queue/c0/done 2>/dev/null | wc -l); grep -aoE "round [0-9]+: [0-9]+ ks -> [0-9]+ advance" $R/hunt_s$S.log | sort > /tmp/lg_B.txt
# ---- compare ----
echo "--- folds A ---"; cat /tmp/lg_A.txt; echo "--- folds B ---"; cat /tmp/lg_B.txt
echo "finish A: $(wc -l < $R/finish_A.log) lines | finish B: $(wc -l < $R/finish_B.log) lines | served A $DONE_A B $DONE_B"
if [ -s /tmp/lg_A.txt ] && cmp -s /tmp/lg_A.txt /tmp/lg_B.txt && cmp -s <(sort $R/finish_A.log) <(sort $R/finish_B.log) && [ "$DONE_A" = "$DONE_B" ]; then echo "G-LADDER replay: PASS"; else echo "G-LADDER replay: FAIL"; exit 2; fi
