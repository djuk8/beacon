#!/bin/bash
# install_make.sh -- put the gated C make into the theater dir. Safe while loops run: every make is a fresh
# process, files are swapped atomically, and any mix of old/new scanhunt x old/new fastmake is a valid pair.
# Backs up the production files with their hash in the name; prints the receipt.  (C, 2026-08-21)
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); R=${THEATER:-$HOME/beacon/raid610}
[ -f "$HERE/fastmake_c.so" ] || { echo "fastmake_c.so missing -- run gate_make.sh first (it builds it)"; exit 1; }
cd "$R" || exit 1
for f in scanhunt_v0.py fastmake.py; do [ -f "$f" ] && { h=$(sha256sum "$f" | cut -c1-12); cp -p "$f" "$f.bak_$h"; echo "backup $f.bak_$h"; }; done
for f in fastmake_numpy.py fastmake_c.so fastmake.py scanhunt_v0.py; do cp "$HERE/$f" "$R/$f.new" && mv -f "$R/$f.new" "$R/$f"; done
echo "installed in $R:"; for f in scanhunt_v0.py fastmake.py fastmake_numpy.py fastmake_c.so; do echo "  $f $(sha256sum "$f" | cut -c1-12)"; done
echo "LINEAGE: scanhunt raid 4e0ce15ddb95 -> $(sha256sum scanhunt_v0.py | cut -c1-12) (v0.1 stable argsort + C pack); fastmake c729c7dc98eb -> $(sha256sum fastmake.py | cut -c1-12) (C kernel $(sha256sum fastmake_c.so | cut -c1-12))"
cd /tmp && rm -rf im_check && mkdir im_check && cd im_check && cp "$R/resonance_map.py" . 2>/dev/null; FASTMAKE_SO="$R/fastmake_c.so" PYTHONPATH="$R" python3 -c "import fastmake; print('smoke: fastmake IMPL =', fastmake.IMPL)"
