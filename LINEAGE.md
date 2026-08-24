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
| cuda: build_residue_table.py | box1 ~/beacon/p3 | 32618f928ad8 | G-A0 lineage |
| cuda: build_residue_table_ab.py | box1 ~/beacon/p3 | 203c0377f91e | G-A0 lineage |
| cuda: check_records.py | box1 ~/beacon/p3 | c3569dceda65 | G-A0 lineage |
| cuda: g1_fermat.cu | box1 ~/beacon/p3 | a90aef0a5a90 | G-A0 lineage |
| cuda: g1_fermat_v2.cu | box1 ~/beacon/p3 | 70e82fe1753d | G-A0 lineage |
| cuda: g2_harness.py | box1 ~/beacon/p3 | d05ffd9f93d4 | G-A0 lineage |
| cuda: gate_ab.py | box1 ~/beacon/p3 | 89919be9d942 | G-A0 lineage |
| cuda: gate_g.py | box1 ~/beacon/p3 | b6124f066512 | G-A0 lineage |
| cuda: livefire_g.py | box1 ~/beacon/p3 | bfa0488e95d8 | G-A0 lineage |
| cuda: livefire_gw.py | box1 ~/beacon/p3 | cd0a7780b798 | G-A0 lineage |
| cuda: mockdrv.py | box1 ~/beacon/p3 | 8d5389ef445d | G-A0 lineage |
| cuda: net_doctor.py | box1 ~/beacon/p3 | 0152d971fc7d | G-A0 lineage |
| cuda: g1_fermat_v2 | box1 ~/beacon/p3 | 4991e2ed66b5 | G-A0 lineage |
CLOSED 08-16: cuda sources + certified binary consolidated.
Deploy rule: repo=archive; NEVER sync repo->live theater mid-campaign.

## O1 + crown consolidation (2026-08-24)
| file | source | sha256[:12] | certification |
|---|---|---|---|
| theater/raid610/scanhunt_v0.py | box1 o1_kit v4.3 | 61622e01ae39 | v0.1 stable argsort + C pack; G-M1/M2 byte/set-identical (was 4e0ce15ddb95) |
| tools/fastmake.py | box1 o1_kit v4.3 | e7219fa0df2a | C dispatch wrapper; G-M1/M2 (was c729c7dc98eb -> tools/fastmake_numpy.py) |
| tools/fastmake_numpy.py | box1 o1_kit v4.3 | c729c7dc98eb | the former fastmake.py, byte-for-byte fallback |
| tools/fastmake_c.c | box1 o1_kit v4.3 | 01fd677db773 | x8.3 sieve kernel + packer; byte-gated |
| tools/ee_serve.py | box1 o1_kit v4.3 | 0cfacb59b9d1 | v2.1 feeder: lanes, gather lock, driver-ee; S1-S7 PASS |
| cuda/g1_fermat_v3.cu | box1 o1_kit v4.3 | f1b64d4fd752 | v3.3 in-driver early exit + --bins + --lock; R0-R3+R2b PASS, 514k t/s |
| theater/raid610/raid_loop_v2.sh | box1 o1_kit v4.3 | c6965db96a78 | v2.4 venue knob, shm cycle, feeder-absent-only fallback |
| theater/raid610/onstart_raid_v2.sh | box1 o1_kit v4.3 | 0d0fc6f604c4 | watchdog target: feeders+loops, venue seed bands, flock |
| theater/raid610/ladder_crown.py | box1 o1_kit v4.3 | 8efb452f46a3 | 3-line diff from ladder610.py 928ae7c00c33; G-L1/G-L2 PASS |
| theater/raid610/ladder_crown.json | box1 o1_kit v4.3 | d8e2c634a056 | crown edges 1568..31576 cap 45.0, frozen 2026-08-23 |
Constants of record: box1 crown 27,550 w/s, t/w 67.2, 0.01488 beta_eff (docs/CROWN_CALC_v1_RC5.md, docs/MACHINERY_v1.md).
