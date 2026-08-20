# Appendix B. Instruments and fingerprints
Core fingerprint (executed at every import; drift aborts):
 monument sigma 0.3576 (+0.07%), strike 0.4897 (-0.01%),
 record 0.5391 (+0.20%).
GPU kernel gate: 2,008,000-verdict known-answer corpus across all
residue classes, zero mismatches; Gerbicz check per production
test (zero alarms across 18.5M+ verdicts).
Sieve gates: byte-exact candidate comparison between the
production landing sieve and an independent dense implementation;
ladder cum-E within 2% or hard fail.
Canonical tool lineage (SHA-256, first 12): scanhunt 4e0ce15ddb95,
fastmake c729c7dc98eb, raid_loop 75817a9c84d4, salvage
3371292b2bb8, ladder610 928ae7c00c33, pfgw_drv 7e94c7a0ac5d,
shard_walk 417aaa0a1e7a. Public snapshot ships MANIFEST.sha256
over every file; the data deposit carries its own DOI: [SLOT].
