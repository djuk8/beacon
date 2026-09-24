# Repo cleanup - the fresh-box release (shredder ~/lab/beacon), 2026-09-24

    cd ~/lab/beacon
    tar xzf ~/beacon_repo_update_20260922.tgz && cat LINEAGE_APPEND.md >> LINEAGE.md && rm LINEAGE_APPEND.md    # September patch, if not yet applied
    sha256sum -c STAMP_20260922.sha256 --quiet && echo "september stamp verifies"
    tar xzf ~/beacon_repo_update3_20260924.tgz          # this patch: kit v8.52, fresh_box.sh, fixed onstart/go_crown/daily, resonance_map in tools/, .gitignore, README script
    python3 apply_readme.py && rm apply_readme.py       # README: stale launch paragraph out, quick start in
    git mv deploy/kit_v1 history/kit_v1_2026-08 && git rm --cached -q history/kit_v1_2026-08/g1_fermat_v2 2>/dev/null; rm -f history/kit_v1_2026-08/g1_fermat_v2   # no binaries in git
    git rm --cached -q deploy/kit_v8/o1_kit_v8.51.tgz 2>/dev/null; rm -f deploy/kit_v8/o1_kit_v8.51.tgz   # one kit tarball, the current one
    cat >> LINEAGE.md <<'EOT'

## 2026-09-24 - the fresh-box release
First deploy of the framework on a machine that is not box1 (4x RTX 5090 rental): ten defects found and fixed in one pass - the kit tarball's nested o1_kit/ extraction; ladder_crown.json and resonance_map.py not shipped in the kit; g1_fermat_v3 depends on NVlabs CGBN and must be compiled from a directory adjacent to it; go_crown assumed box1's crontab backup (the watchdog was silently not armed) and box1's seeds; daily.sh failed with no ledger; the README still described the August kit as the stand-up. Fixed in kit v8.52 (SIEVESEED.txt knob in onstart, go_crown builds its crontab from scratch and takes the ladder design and resonance_map from the kit, daily.sh tolerates a fresh box) and deploy/fresh_box.sh, which reproduces the whole stand-up. The rental box runs seed 2500 (k0 2.1e13), disjoint from box1's range.
EOT
    git add -A && git commit -q -m "September 2026: fresh-box release - kit v8.52, deploy/fresh_box.sh, README quick start, defects from the first fresh deploy fixed" && git log --oneline | head -2
    find . -type f -not -path './.git/*' -exec sha256sum {} + | sort -k2 > STAMP_20260924.sha256 && git add STAMP_20260924.sha256 && git commit -q -m "stamp 2026-09-24" && sha256sum -c STAMP_20260924.sha256 --quiet && echo "stamp verifies"

Then the proof: on the rental box (or the next one), from a clean clone,  bash deploy/fresh_box.sh --seed 3000  and nothing but the daily read afterwards.
