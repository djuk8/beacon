#!/bin/bash
# nogec_deploy.sh -- swap the hunt's driver to the GEC-free build (atomic; running drivers finish on the old one), keep the GEC build for
# rollback, and arm the hourly canary: every card runs 400 known candidates (200 prime) and must match the GEC-gated verdicts byte for byte.
# Rollback any time:  cp -p /root/beacon/p3/g1_fermat_v3.gec /root/beacon/p3/g1_fermat_v3
set -eu; P3=/root/beacon/p3; cd $P3
[ -x g1_nogec ] && [ -f canary_2048.bin ] && [ -f canary_expected.bin ] || { echo "run nogec_gate.sh first"; exit 1; }
[ -f g1_fermat_v3.gec ] || cp -p g1_fermat_v3 g1_fermat_v3.gec
cp g1_nogec g1_fermat_v3.new && mv g1_fermat_v3.new g1_fermat_v3 && echo "driver swapped to NOGEC: $(sha256sum g1_fermat_v3 | cut -c1-12) (GEC kept as g1_fermat_v3.gec)"
cat > canary.sh <<'EOT'
#!/bin/bash
# hourly canary: a sick card turns known primes into "composite" -- every card must reproduce the gated verdicts exactly
cd /root/beacon/p3; NG=$(nvidia-smi -L | wc -l)
for d in $(seq 0 $((NG-1))); do ./g1_fermat_v3 canary_2048.bin /tmp/canary_v$d.bin --device $d > /dev/null 2>&1
  if cmp -s /tmp/canary_v$d.bin canary_expected.bin; then r=OK; else r=FAIL; fi; echo "$(date -u +%FT%TZ) card $d $r"; done >> /root/beacon/raid610/canary.log
EOT
chmod +x canary.sh && bash canary.sh && tail -$(nvidia-smi -L | wc -l) /root/beacon/raid610/canary.log
( crontab -l 2>/dev/null; echo "43 * * * * /root/beacon/p3/canary.sh" ) | sort -u | crontab - && echo "canary armed hourly at :43; check: grep FAIL /root/beacon/raid610/canary.log"
