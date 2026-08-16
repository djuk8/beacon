# BEACON canonical lineages (consolidation 2026-08-16)
| file | source | sha256[:12] | certification |
|---|---|---|---|
| theater/raid610/scanhunt_v0.py | box3/raid610 | 4e0ce15ddb95 | fastmake hook + 4e9 span; G-F1/F2 + live bands |
| tools/fastmake.py | box3/raid610 | c729c7dc98eb | byte-identity vs legacy + ladder610 gate; chunk=256 |
| theater/raid610/raid_loop.sh | box3 (de-pinned) | 75817a9c84d4→edited | flock+retry+cleanup(le5)+Q1e5; PYBIN pinned at install |
| tools/salvage_v0.py | box1==box3/arch6150 | 3371292b2bb8 | v0.2: fsync ledger+lock+keep-unresolved (hash-twin) |
| theater/raid610/ladder610.py | box1 | 928ae7c00c33 | sort-stability fix; frozen edges in ladder610.json |
| tools/pfgw_drv.py | mono | 7e94c7a0ac5d | MAGIC_V writer fix (landmine 7 closed) |
| tools/shard_walk.py | mono | 417aaa0a1e7a | equivalence-proven sieve; buffered; rename-guarded |
| exchange/* | shredder deployed | — | v1 knots + measured GPU ladder + wall mode; selftest PASS |
OPEN: g1_fermat_v2.cu single-site on box1 ~/beacon/p3 (relay owed).
Deploy rule: repo=archive; NEVER sync repo->live theater mid-campaign.
