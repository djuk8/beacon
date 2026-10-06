#!/bin/bash
# hourly canary (v8.55): every card runs 400 known candidates (200 prime) through the production driver; the verdicts must match the
# expected ones byte for byte. A sick card turns known primes into "composite". Log: /root/beacon/raid610/canary.log (grep FAIL).
cd /root/beacon/p3; NG=$(nvidia-smi -L | wc -l)
for d in $(seq 0 $((NG-1))); do ./g1_fermat_v3 canary_2048.bin /tmp/canary_v$d.bin --device $d > /dev/null 2>&1
  if cmp -s /tmp/canary_v$d.bin canary_expected.bin; then r=OK; else r=FAIL; fi; echo "$(date -u +%FT%TZ) card $d $r"; done >> /root/beacon/raid610/canary.log
