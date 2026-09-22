#!/bin/bash
# expq.sh -- run a queue of experiments unattended. queue file: one per line "NAME KEY=VAL ...", '#' comments.
# usage: setsid nohup bash expq.sh queue.txt > expq.log 2>&1 &     (results accumulate in ~/beacon/raid610/experiments.log)
set -u
K=$HOME/beacon/p3/o1_kit
grep -v '^\s*#' "$1" | grep -v '^\s*$' | while read -r NAME ARGS; do
  echo "$(date -u +%T) starting $NAME $ARGS"
  env -i HOME=$HOME PATH=$PATH bash $K/exp.sh $NAME $ARGS || { echo "$(date -u +%T) ABORTING QUEUE: $NAME failed its launch check"; exit 1; }
done
echo "$(date -u +%T) queue done -- see ~/beacon/raid610/experiments.log"
