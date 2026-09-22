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

## September consolidation (2026-09-22) -- RC11/RC12 machinery, the record, the records package
| file | source | sha256[:12] | certification |
|---|---|---|---|
| README.md | box1 kit v8.51 / shredder RECORD | ece39c0798b8 | -- |
| records/BEACON_abstract.pdf | box1 kit v8.51 / shredder RECORD | 54ebfe64185a | -- |
| records/RECORDS.md | box1 kit v8.51 / shredder RECORD | ffb5391388dc | -- |
| records/RECORD_README.md | box1 kit v8.51 / shredder RECORD | 02835a11fe70 | -- |
| records/batch1_top20.txt | box1 kit v8.51 / shredder RECORD | 745aa22950bf | 20 gaps in the list 2026-09-22, ECPP-certified |
| records/submission_lines.txt | box1 kit v8.51 / shredder RECORD | dc79d91678f1 | -- |
| records/treasury_all.txt | box1 kit v8.51 / shredder RECORD | 1fe3dc0e0f54 | -- |
| gates/gate_bsd.sh | box1 kit v8.51 / shredder RECORD | 098f756e2ad4 | -- |
| gates/gate_bsd_depth.sh | box1 kit v8.51 / shredder RECORD | 7962a05b0639 | -- |
| gates/gate_bsd_load.sh | box1 kit v8.51 / shredder RECORD | fccbee7d1d70 | -- |
| gates/gate_gbs.sh | box1 kit v8.51 / shredder RECORD | ff398f618061 | -- |
| gates/gate_ladder.sh | box1 kit v8.51 / shredder RECORD | 2b76aaab2bd8 | -- |
| gates/gate_make.sh | box1 kit v8.51 / shredder RECORD | 2e8a0ada52dc | -- |
| gates/gate_o1.sh | box1 kit v8.51 / shredder RECORD | 6f799eca0c88 | -- |
| gates/gate_pred.sh | box1 kit v8.51 / shredder RECORD | 56269a7c2491 | -- |
| gates/gate_r4.sh | box1 kit v8.51 / shredder RECORD | edc23413fdf9 | -- |
| gates/gate_serve.sh | box1 kit v8.51 / shredder RECORD | ad1dd40b8aaf | -- |
| gates/gate_sieve.sh | box1 kit v8.51 / shredder RECORD | 52155e8be8a1 | -- |
| gates/o1_gates.sh | box1 kit v8.51 / shredder RECORD | 0f6a57eb1ca1 | -- |
| gates/gate_o1_stubs/stub_driver.py | box1 kit v8.51 / shredder RECORD | 005519b42f2e | -- |
| gates/gate_o1_stubs/stub_ee_drive.py | box1 kit v8.51 / shredder RECORD | e276c52082bb | -- |
| cuda/g1_fermat_v33.cu | box1 kit v8.51 / shredder RECORD | f1b64d4fd752 | -- |
| cuda/gbs.cu | box1 kit v8.51 / shredder RECORD | eab61d196297 | G-GBS-2/3 (1e8/1e10 byte-identical to make --select 12), G-SV-3/4 via gbsd |
| theater/raid610/box_status.sh | box1 kit v8.51 / shredder RECORD | 74ad5ebee254 | -- |
| theater/raid610/bsd.py | box1 kit v8.51 / shredder RECORD | 821353a59cf5 | CPU sieve daemon; G-BSD-2/4; predictor ranking |
| theater/raid610/daily.sh | box1 kit v8.51 / shredder RECORD | db884d9d4ece | production daily read |
| theater/raid610/exp.sh | box1 kit v8.51 / shredder RECORD | 0640de6a7e13 | experiment runner with launch check |
| theater/raid610/expq.sh | box1 kit v8.51 / shredder RECORD | a612f01be389 | -- |
| theater/raid610/feeder_restart.sh | box1 kit v8.51 / shredder RECORD | fee252553b25 | -- |
| theater/raid610/finish_v34.sh | box1 kit v8.51 / shredder RECORD | 679de3b45276 | -- |
| theater/raid610/gbsd.py | box1 kit v8.51 / shredder RECORD | 6f1a5fc43aea | sieve-card daemon, pooled tail, persistent resume; G-SV-3/4 identity vs bsd at 1e10 |
| theater/raid610/go_crown.sh | box1 kit v8.51 / shredder RECORD | e69153973e13 | -- |
| theater/raid610/go_fourwide.sh | box1 kit v8.51 / shredder RECORD | 564326042087 | -- |
| theater/raid610/harvest_hourly.sh | box1 kit v8.51 / shredder RECORD | 101cb3c03e44 | hourly fossil walk (cron) |
| theater/raid610/install_make.sh | box1 kit v8.51 / shredder RECORD | 5ac7d86bde8a | -- |
| theater/raid610/ladder.py | box1 kit v8.51 / shredder RECORD | 484e10add374 | ladder manager; G-LADDER replay identical to raid_loop_v2.sh |
| theater/raid610/ladder_crown.py | box1 kit v8.51 / shredder RECORD | 8efb452f46a3 | -- |
| theater/raid610/onstart_raid_v2.sh | box1 kit v8.51 / shredder RECORD | 5b6f802bd29f | self-healing singleton lock, setsid -f, core reservation, BSD=3 sieve card |
| theater/raid610/prewarm_cache.py | box1 kit v8.51 / shredder RECORD | 4c4677bc2a1c | -- |
| theater/raid610/raid_loop_v2.sh | box1 kit v8.51 / shredder RECORD | 87ed56ec6d7b | v2.19: consume-or-wait, unique fossil names |
| theater/raid610/salvage_status.sh | box1 kit v8.51 / shredder RECORD | facbd6fb6a55 | -- |
| theater/raid610/sampler.sh | box1 kit v8.51 / shredder RECORD | 20164703122d | -- |
| theater/raid610/scanhunt_v0.py | box1 kit v8.51 / shredder RECORD | 4f1d31ab8823 | -- |
| theater/raid610/shadow_restart_loops.sh | box1 kit v8.51 / shredder RECORD | 8974652d09fa | -- |
| theater/raid610/shadow_start.sh | box1 kit v8.51 / shredder RECORD | 330358e9b4e0 | -- |
| theater/raid610/shadow_status.sh | box1 kit v8.51 / shredder RECORD | e5175000ef5a | -- |
| theater/raid610/stop_theater.sh | box1 kit v8.51 / shredder RECORD | 8a8ce6a3d49b | -- |
| theater/raid610/swap_v34.sh | box1 kit v8.51 / shredder RECORD | 4a3942f31d13 | -- |
| theater/raid610/theater_autopsy.sh | box1 kit v8.51 / shredder RECORD | 6648f66767b9 | -- |
| tools/certify_batch.py | box1 kit v8.51 / shredder RECORD | 8e6112a65f76 | notary + ECPP (CM ecpp) + PARI primecertisvalid per claim |
| tools/claimcheck_v1.py | box1 kit v8.51 / shredder RECORD | aa96ef8aff56 | claims vs per-gap-size table |
| tools/compare_vbin.py | box1 kit v8.51 / shredder RECORD | 6b3501d4a5bd | -- |
| tools/deep_primes.py | box1 kit v8.51 / shredder RECORD | 48af7904f9c1 | -- |
| tools/ee_drive.py | box1 kit v8.51 / shredder RECORD | 79cbea989b83 | -- |
| tools/ee_serve.py | box1 kit v8.51 / shredder RECORD | 79992acb2a80 | -- |
| tools/fastmake.py | box1 kit v8.51 / shredder RECORD | 408617b584a7 | -- |
| tools/fastmake_c.c | box1 kit v8.51 / shredder RECORD | 302b0cf4f798 | -- |
| tools/fastmake_numpy.py | box1 kit v8.51 / shredder RECORD | c729c7dc98eb | -- |
| tools/make_endpoints.py | box1 kit v8.51 / shredder RECORD | 6a64d5b80718 | -- |
| tools/mkrings.py | box1 kit v8.51 / shredder RECORD | 0f7416a85f58 | -- |
| tools/mksizes.py | box1 kit v8.51 / shredder RECORD | 9984df11ee2d | -- |
| tools/notary_v2.py | box1 kit v8.51 / shredder RECORD | c21b5e44ab90 | swap-aware notary + independent next_prime walk; VALID on records |
| tools/replay_compare.py | box1 kit v8.51 / shredder RECORD | d4349b92067a | -- |
| tools/salvage_v0.py | box1 kit v8.51 / shredder RECORD | 4be1e02b53ae | -- |
| tools/salvage_v1.py | box1 kit v8.51 / shredder RECORD | 6df75c09ce8c | accounted harvest walk; selftest vs next_prime |
| tools/sieve/bs_api.c | box1 kit v8.51 / shredder RECORD | 04a4fb1d01bb | threaded partitions + predictor tables; G-PRED |
| tools/sieve/bs_bench_mt.c | box1 kit v8.51 / shredder RECORD | 6b5caabb9800 | -- |
| tools/sieve/bs_bigp.c | box1 kit v8.51 / shredder RECORD | 72b6e9ce9ee3 | large-p referee to 1e10 |
| tools/sieve/bsieve.c | box1 kit v8.51 / shredder RECORD | 7d52f25f89a1 | referee 466M checks; G-BSD-2 (make identity 1e8), G-BSD-4 (depth identity 1e10) |
| tools/sieve/fh_big.c | box1 kit v8.51 / shredder RECORD | 9fd95a627d3f | first-hit referee to 1e10 |
| tools/sieve/fk_walk.c | box1 kit v8.51 / shredder RECORD | 37b0238e1e67 | FK lattice walk, 50k-trial referee |
| docs/BUCKET_SIEVE_STATUS.md | box1 kit v8.51 / shredder RECORD | e1354b878f78 | -- |
| docs/CROWN_CALC_v1_RC11.md | box1 kit v8.51 / shredder RECORD | df90d90ba6ca | -- |
| docs/CROWN_CALC_v1_RC9.md | box1 kit v8.51 / shredder RECORD | e4f06c33349d | -- |
| docs/CROWN_LADDER_PREREG.md | box1 kit v8.51 / shredder RECORD | 12e1961fbc45 | -- |
| docs/MACHINERY_v1.md | box1 kit v8.51 / shredder RECORD | e38da06024d1 | -- |
| docs/O1_ROLLOUT_PLAN.md | box1 kit v8.51 / shredder RECORD | 44cbeb68bd74 | -- |
| docs/O3_STATUS.md | box1 kit v8.51 / shredder RECORD | d0d266795801 | -- |
| docs/PRED_NOTE.md | box1 kit v8.51 / shredder RECORD | 4685505fef22 | -- |
| docs/RAID610_PREREG.md | box1 kit v8.51 / shredder RECORD | b4613299d0b7 | -- |
| docs/RUNG_PROFILE_NOTE.md | box1 kit v8.51 / shredder RECORD | 57cbb953ef10 | -- |
| docs/SELECT_PREREG.md | box1 kit v8.51 / shredder RECORD | 501a20c09cc9 | -- |
| docs/session_handoff_20.md | box1 kit v8.51 / shredder RECORD | c57e25d24fc7 | -- |
| docs/session_handoff_21.md | box1 kit v8.51 / shredder RECORD | 8c4317ed35d0 | -- |
| deploy/kit_v8/o1_kit_v8.51.tgz | as deployed on box1 2026-09-21 | 7216a839881b | sha 7216a839881b3051 |
Deploy rule unchanged: repo=archive; NEVER sync repo->live theater mid-campaign.
