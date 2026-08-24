# O1 ROLLOUT PLAN -- composition early-exit over the certified binary
# AUTOMATED: o1_gates.sh runs sec 1.1-1.5 (G0 preflight+soak read, G1 harness,
# G2 replay x3, G3 geometry+feed) as one paste; this file is the reference.
# (C, 2026-08-21; companion to session_handoff_19.md; frozen numbers from
#  CROWN_CALC v1-RC2 / handoff 18 sec.2; nothing here re-freezes anything)

## 0. VERDICT ON DIRECTION
Right direction, with two teeth-checks and one physics caveat.
- RIGHT: early exit as an orchestration layer (ee_drive) over the UNCHANGED
  g1_fermat_v2 keeps the G-A0 certificate (2,008,000 verdicts) intact; no
  driver re-gate. The saving is exact physics, not a model: every window
  dies exactly once, so tests/window -> (1/beta)(1-e^-E) ~ 1/beta = 57.3
  (+ chunk overshoot) against the deployed CL/beta = 121.2.  x2.08, same
  as the frozen sheet (57.9). Nothing to re-derive.
- TEETH: gate_o1.sh v1.1 could not fail. Stage B's five rings contain zero
  primes (checked with gmpy2 on the exact seeded construction: P(21-ring
  has a prime) = 2.9%), so early exit was never exercised; stage A did not
  count composite->PRP, so an all-ones driver passed; no MAGIC_V check;
  gmpy2-absent = PASS.  v1.2 (shipped) plants known primes + decoys, checks
  the output header, counts both mismatch rows, binds the driver hash to
  CERT_SHA, and was negative-tested in the sandbox (fake early exit -> B
  FAIL; all-ones driver -> A FAIL; wrong hash -> stop).  v1 was mine (C).
- PHYSICS CAVEAT (decides the shadow-hour design): the test saving is
  certain; the WALL saving is not.  Per-loop waves shrink the batch as k's
  die (wave w carries 8 x N_k x 0.869^(w-1)), and each wave is a fresh
  driver process = fresh CUDA context.  At the R1 geometry (~30 loops/card,
  ~7 s make, ~840 windows/ring [MODEL from 14.5k w/s, read actual ring size
  off a box1 manifest]) that is ~51 launches/s/card; cold start >= 50 ms
  means the card spends more time creating contexts than testing, and the
  final waves (~1.4k candidates) under-fill a 5090.  Stage C (cold start)
  and the new stage D (throughput knee) measure exactly this.  Expected
  outcome: geometry must change -- few loops per card (2-4), big rings
  (>= 6k windows), make/drive pipelined -- which needs NO aggregator and NO
  binary change.  If even that fails D's knee, the fallbacks in order are:
  CUDA MPS on the box (one line, no code), a per-card aggregator
  (ee_serve), and last the in-driver early exit from the 18 build order
  (binary change => G-A0-class re-gate).

## 1. STEP 1 -- BOX1: GATE, REPLAY, SHADOW, FLIP, BURN, GO-RULE, FIRE
(each line is a stop point; nothing advances on a red line)

1.1 Soak status first (pass = boring + >=1 observed self-resurrection).
    Read, do not run anything else until the soak verdict is written:
      tail -n 40 /root/watchdog.log ; ls -t <manifest dir>/*.json | sed -n 2p
    If the soak has not produced a natural resurrection: do NOT wait for
    one.  Run a FIRE DRILL: kill -9 one seed, confirm the */10 watchdog
    brings it back (<= 10 min), log it as the observed resurrection.  The
    drill is the doctrine's test executed on purpose; it is what makes a
    24-h timeline possible at all (sec 1.8).

1.2 Upload ee_drive.py and the new loop to this session before the gate
    runs (read the source before guessing -- the harness encodes an
    assumed CLI/file contract; one read of ee_drive confirms or corrects
    it; grep its MAGIC constants against the driver source).

1.3 G-O1 on box1, GPU 0, ~3-5 min, read-only on the theater (note the
    window in the soak log so the dip is not misread):
      cd ~/beacon/p3 && PY=/venv/main/bin/python3 GPU=0 \
        CERT_SHA=$(awk '/g1_fermat_v2/{print $1}' <kit_v1 manifest>) \
        bash gate_o1.sh 2>&1 | tail -40
    Pass = "A: PASS", "B: all checks PASS", C and D printed.  Record from
    C: cold-start ms.  From D: knee N and peak t/s (peak should reproduce
    516,358 t/s within the usual few %; if not, the card or the file
    contract is not what we think -- stop).  gmpy2 missing in the venv is
    a STOP (exit 2), not a pass.

1.4 Step-2 replay on three fossil trios (the pre-kit-era r04/r05 orphans,
    handoff 18 sec.9; never touched, copied to /tmp by the tool):
      for f in <three gl_NNNN.bin fixtures>; do
        /venv/main/bin/python3 replay_compare.py $f --gpu 0 --legacy-time \
          --py /venv/main/bin/python3 | tail -6; done
    Pass = REPLAY PASS x3, verdict mismatches 0, tests ratio ~0.48-0.55
    at the ring geometry (= ideal constant-chunk figure printed beside
    it), wall ratio printed.  The wall ratio on one ring in one process
    is the first honest datum for the caveat in sec 0.

1.5 Geometry decision from C + D (15 min, paper only):
      launches/s/card = loops_per_card x waves_per_ring / make_period_s
      overhead = launches/s x cold_s        (need <= 0.10)
      last-wave batch = 8 x windows_per_ring x 0.869^(waves-1)  (need >= knee)
    Pick (loops/card, windows/ring) satisfying both; with make pipelined
    the make period is hidden behind the GPU, so the only cost of big
    rings is memory.  Write the chosen geometry into the kit as constants
    (grep-verify every constant you did NOT change -- KB=10000 lesson).

1.6 Shadow hour: 1 card, 1 bay, O1 loop at the chosen geometry, legacy
    on the other three cards.  Measures (all from manifests, era-cut:
    2nd-newest manifest, tail-sample logs): windows/s per card, tests/
    window (target 58-65), beta_eff = PRPs / TESTED (not / shell size --
    the estimator changes under early exit; the fold must consume
    tested.json), survivor rate per rung vs ladder610 cum_e, zero verdict
    disagreement on any ring also run legacy (spot 3 rings through
    replay_compare against the shadow's own v.bin).  Then the fire drill
    on the O1 loop: kill -9 -> resurrected by the watchdog pattern (the
    sh wrapper must match the NEW process name; the cron line stays
    pattern-free).  Pass = all five numbers in band + drill observed.
    Operational hygiene for the new loop (all struck before, all fatal):
    setsid + PYTHONUNBUFFERED=1; absolute PYBIN; wave temp files in a
    private tmp dir, never in the ring dir (a sweep glob or the R2
    age-gate must not be able to see them); age-gate -mmin +5 re-verified
    against the longest ring lifetime at the new geometry; FINALIST_*
    STOP guard honoured; no 2>/dev/null anywhere near a copy that feeds a
    kit; MAGIC_C/MAGIC_V grep in ee_drive against the driver source.

1.7 Flip box1 (4 cards) to the O1 composition = kit_v1.1: ee_drive + new
    loop + watchdog wrapper + fold estimator + geometry constants;
    LINEAGE sha:12 for every new file; R5 runbook <= 30 min written while
    doing it (this IS the stand-up rehearsal for the rented boxes).
    Freeze kit_v1.1 with hashes before the burn starts.

1.8 24-h burn on box1 under kit_v1.1.  Pass = boring + tests/window and
    beta_eff stable over 24 h + >=1 resurrection (drill or natural) + R2
    salvage crontab's first meal (the fossil inventory) digested without
    touching a live file.  In parallel, zero-meter:
      G-K2: kappa_2 at the crown window (run_kappa2.py with J=29,743)
      -> second-order term on -lnP (expect ~+0.05, i.e. x1.05 on cost);
      CROWN_CALC v1 FINAL: replace the 57.9 t/w MODEL with the MEASURED
      shadow/burn number, add the G-K2 term, both signatures, hash.

1.9 GO-RULE (frozen, RC2): fire only if the gated number <= 20-22 days
    on the contracted fleet (40 cards).  Reading it honestly:
      Plan A crown (m > 41.93878): post-O1 1,527 card-days median =
        38 d median / ~61 d at 80% on 40 cards  -> NO-GO on O1 alone.
        Becomes GO only with O3-GPU@1e12 (760 cd = 19.0 d) or
        O3-GPU@1e9 + O4*O5 >= 1.27 -- week-2 items, not 24 h.
      Plan C decapitate #2-#6 (m >= 39.7): ~7 d median / 17 d at 80% on
        40 cards post-O1  -> GO-able 24 h after a green burn.
      Both x~1.05 once G-K2 lands.  The by-catch at Plan C still owns
      the top ~6 slots; the crown stays the week-2 campaign.
    "24 hours later start the record run" therefore means Plan C, unless
    you consciously override the rule you froze (your call; no overclaim
    either way, and the ledger records which plan fired and why).

1.10 Fire sequence (Plan C or A, identical mechanics): claimcheck the
    target merits vs gaps.db AND the 84,777 staging queue first (Renyer
    active); rent 5x8 across >= 3 landlords; stand up each box from the
    runbook (<= 30 min); G-O1 stages A + D on each box (5 min -- proves
    the binary and the knee on THAT card); fire drill per box (15 min,
    the observed resurrection); then fire.  Preregister the campaign
    (prereg file: plan, merit line, fleet, t/w used, go-rule arithmetic,
    stop rule) before the first seed starts.  Treasury freeze unchanged.

## 2. STEP 2 -- CALCULATORS, THEN FREEZE
2.1 pricer v2.4 -> v2.5: t/w constants = MEASURED post-O1 (shadow+burn),
    G-K2 second-order term, Theta normalization made explicit (P1 in
    handoff 19: exact product vs Mertens form -- pick one, fingerprint).
2.2 CROWN_CALC v1 FINAL (sec 1.8) -- the only document the go-rule reads.
2.3 arbitrage_map v1.1 -> v1.2: rerun the 121,457-row repricing with the
    v2.5 constants (the "boards rerun" in the agreed order of play);
    diff against v1.1 -- the ranking should be invariant, the absolute
    costs move by the t/w and G-K2 factors.
2.4 COST_CALCULUS.md rewrite with the 08-21 constants (owed since
    handoff 14; A-band retired; 2,150 t/s retired; class ladder replaces
    D^3); dated header; or move to history/ (decision, handoff 19 sec 3).
2.5 Freeze: fingerprints for sigma_t1 (if P1 changes it), pricer v2.5,
    arbitrage v1.2, CROWN_CALC FINAL; selftests run; LINEAGE updated.

## 3. STEP 3 -- GIT: WHAT SHIPS, WHAT DOES NOT
3.1 Land in the private repo (archive): ee_drive.py, the O1 loop, kit_v1.1
    (deploy/), gate_o1.sh v1.2 + gate_o1.log as receipts, replay_compare.py,
    td_indep.py (tools/, kept independent of sigma_t1), gates/
    REFEREE_PREREG.md + RECEIPTS_referee_0821.txt, run_kappa2*.py,
    CROWN_CALC FINAL, pricer v2.5, arbitrage v1.2; LINEAGE entries for all.
3.2 README.md rewritten for the public reader: what the law is (one
    paragraph), what the tools do (evaluator, pricer, arbitrage map,
    gates), how to reproduce Sec 5 (td_indep + the 20-row artifact table),
    licenses (Apache-2.0 code / CC BY 4.0 docs+data), citation block (DOI
    slot), AI-disclosure pointer (Appendix A), no theater/ops content.
3.3 export_public.sh regenerated (handoff 19 sec 3): INCLUDE-list only
    (tools gates exchange cuda theory/t1 paper docs/{MISSION,COST_CALCULUS,
    RUNBOOK_STANDUP}.md README LINEAGE LICENSE NOTICE LICENSE-DOCS);
    scrub-by-name (*state*.json, *private_notes*, handoffs, treasury,
    rental, competitor material, hygiene per-discoverer notes); secrets
    grep (IPs, hostnames, root@, ssh, tokens, vault paths, landlord
    names); fresh gate run ON THE SNAPSHOT; sha256 manifest; no
    2>/dev/null; dry run -> diff listing -> your eyes -> tag.
3.4 Stale docs on the include-list fixed or moved (sec 2.4 + MISSION.md).
3.5 Tag -> GitHub-Zenodo webhook -> DOI reserved BEFORE any disclosure
    (DOI first; viXra never; vault = separate data deposit with its own
    DOI: the 20-row artifact table, gaps.db snapshot, manifests used in
    Sec 5, the combined_sieve unknowns files behind Sec 5.6).

## 4. STEP 4 -- ARXIV NEAR-FINAL
4.1 Decisions A (handoff 19 sec 4): 3.9 withdraw/demote; D1 wording;
    Table 6.1 three-row form; Appendix A in the PDF; endorsement
    sequencing (parade-then-endorse vs endorse-then-parade).
4.2 arxiv_patch3.sh (one idempotent, guard-checked installer, bash -n +
    smoke, shipped as a file): P1 Theta sentence/evaluator; P2 Sec 5.1
    window convention + artifact table pointer; P3 Ex 3.5 wording + the
    d-(D,m) map line in 6.5; P4 3.9/5.4/abstract; P5 Sec 5.6 Fano 0.631
    (decomposition) + Prop 2.6(c) second-order sentence; P6 Table 6.1;
    P7 rung footnote; P8 CITATIONS_MAP; P9 recount; P12 (h) policy; plus
    O1 as MEASURED in Sec 4.1/6.1 (tests/window with CI, geometry).
4.3 Content freeze -> LaTeX conversion -> bibliography final check
    (Maier 1985, Hardy-Littlewood, Mertens, Buchstab/Dickman/de Bruijn
    still KNOWLEDGE-status) -> Appendix A verbatim -> abstract bracket
    resolved by the parade decision -> DOI in 7.3 -> endorsement email
    per the rewritten arxiv_plan.md (one endorser at a time, 5-7 days).

## 5. STEP 5 -- THE SWEEP (sanity, sync, "did we miss something")
Run as a checklist with receipts; each item gets a line in gates_log.
5.1 Binary/kit sync: sha256 of g1_fermat_v2 on box1 == kit_v1 cert hash
    == repo cuda/ build record; ee_drive/loop on box1 == kit_v1.1 hashes.
5.2 Shredder deployed copies vs repo: DS7/DS8 deepsieve.py + gate_ds.py
    at /usr/local/bin/primes/prime_gap are AHEAD of project copies --
    sync before reuse; diff every tool in LINEAGE against its sha:12.
5.3 Evaluator cross-check: td_indep vs sigma_t1 on the 20 Sec-5.2 rows,
    the 7 raid610 ring targets, the 3 campaign rows, the 5 design rows
    (settles P1; any row off by > 0.3% is a finding, not noise).
5.4 Treasury claimchecks (before any parade planning): 426,520 / 52,868 /
    52,376 / 209,420 / 201,646 / 1,348,726 / 1,263,196 / 1,118,828 vs
    gaps.db AND staging 84,777; Crown-3 third proof on shredder (gmpy2,
    shard_walk --finalist); mono receipts (pfgw -b2 both endpoints via
    the submission expression -> receipts_mono.txt, private cwd per
    shard, parse output never exit codes).
5.5 k-recovery via RNG replay for the 220 stranded box1 finds (dirs
    w5001-5004, w5101-5103 -- read-only, never overwrite).
5.6 Fold-stat re-derivation: beta_eff from box1 manifests under legacy
    (0.01744) and under O1 (tested-count estimator) -- must agree within
    their CIs; fix the scanhunt docstring (300-400 -> 120-143).
5.7 Magic-constant grep across every writer (MAGIC_C/MAGIC_V in driver,
    ee_drive, fold, salvage) -- one grep, one receipt.
5.8 Watchdog: cron lines pattern-free; wrapper patterns match the
    kit_v1.1 process names; @reboot + */10 pair present on every box.
5.9 Census stragglers (waves/ submission machinery, beacon_box3.tgz,
    bench/kit3/eu/CGBN) classified: keep / history / delete, with
    receipts.
5.10 Paper numbers vs sources: every number in the paper traceable to a
    gate verdict or a file in the deposit (the freeze gate for P1-P12);
    hygiene rows' (h) marks re-derived from the data, not from memory.
5.11 Parade timing: Renyer/VGautier activity read from the staging queue
    the day before; honor-guard order largest-first; one tribute post;
    Troisi generous; DOI already minted.

## 6. STOP POINTS SUMMARY (where I wait for you)
S1 soak verdict written (1.1)      S2 ee_drive.py in hand (1.2)
S3 G-O1 output read (1.3)          S4 geometry chosen (1.5)
S5 shadow-hour numbers (1.6)       S6 burn verdict + CROWN_CALC FINAL (1.8)
S7 plan chosen under the go-rule (1.9)   S8 decisions A for the paper (4.1)
