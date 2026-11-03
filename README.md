# BEACON — Prime Gap Records by Design

*A measured cost law for prime-gap records, and the pipeline that hunts
them.* 
---

## Quick start - a fresh GPU box in one command

Any Linux machine with NVIDIA GPUs, the CUDA 12 toolkit, gcc, git, python3 and pari-gp:

    python3 -m pip install numpy gmpy2
    git clone https://github.com/djuk8/beacon ~/lab/beacon && cd ~/lab/beacon
    bash deploy/fresh_box.sh --seed 2500

`fresh_box.sh` extracts the kit, clones NVlabs' CGBN and builds the GPU Fermat driver for your card, writes the venue and seed files, builds the residue cache (about 15 minutes), builds the C and CUDA sieve, runs the identity gate (the GPU sieve against an independent CPU sieve, byte for byte) and launches the hunt with a watchdog that relaunches anything that dies. Twenty minutes later:

    bash ~/beacon/p3/o1_kit/daily.sh

prints throughput per four-hour slice, the fossil audit, the harvest and the day's best gaps. A healthy box reads about 11,000 windows/s per RTX 5090 with all GPUs at 100% (the first hour ramps). Every gap the hourly harvest walks lands in `~/beacon/raid610/campaign_ledger.log`; `tools/notary_v2.py` re-derives any gap from its tuple, `tools/certify_batch.py` proves the endpoints with ECPP, and the lines those tools print go to the Prime Gap List's submission server.

The seed picks the k-range: k0 = 10^12 + 8·10^9·seed, and boxes must not share one (box1 ran seed 2004; use 2500, 3000, 3500 ... for new machines). The current tree is stamped by `STAMP_20261103.sha256`; `sha256sum -c STAMP_20261103.sha256 --quiet` verifies it. Since v8.56 a sieve daemon can hunt one residue class of k mod 2310 (knob files SIEVESTEP / SIEVECLASS / SIEVEKBASE / SIEVEBID, see `KIT_v8.56_NOTE.md`); without them a box runs exactly as v8.55.

## 1. The game, from zero

A **prime gap** is the distance between two consecutive prime numbers.
Between 23 and 29 there is a gap of 6. Gaps grow — on average — like
the natural logarithm of the numbers involved, so raw gap size mostly
tells you *where* you looked, not how remarkable the find is. The
community therefore scores gaps by **merit**:

> **merit = gap / ln(p₁)** — how many times larger the gap is than an
> average gap at that height (p₁ is the prime that starts the gap).

A merit of 20 means "twenty average gaps' worth of nothing, in one
stretch." The [prime gap list](https://github.com/primegap-list-project/prime-gap-list)
tracks every first-known and record gap — over 120,000 entries — and
several leaderboards sit on top of it: the **all-time merit table**
(highest merits ever, any size), **size tables at merit thresholds**
("largest gap with merit ≥ 20 / ≥ 30"), and per-gapsize
**first-occurrence records** (smallest starting prime known for each
gap size). People have hunted these tables for decades, mostly by
searching enormous ranges and hoping.

**BEACON's thesis: hope is the expensive part.** Record gaps can be
*designed* — placed where mathematics makes them cheap — and the cost
of any record on any table can be *priced in advance* by a measured
law. This repo is the law, the machinery, the verification chain, and
the receipts.

## 2. The idea in four steps

**(a) Choose where the gap lives.** Instead of scanning random
territory, center the search at numbers of the form

> **n₀ = k · zd# / d**

where `zd#` is a **primorial** (the product of all primes up to `zd`),
`d` is a small divisor of it, and `k` is a small integer. Around such
n₀, divisibility is not random: every prime p ≤ zd (except those
dividing d) automatically divides n₀, so it can only "interrupt" the
gap at positions j that are multiples of p. The neighborhood of n₀ is
born mostly empty. The offsets j where a prime *could* live — the
**survivors** — are few and known in advance.

**(b) Sieve, don't test.** A cheap sieve (all primes up to Q, typically
10⁵–10⁹) removes every position with a small factor. What remains gets
a real primality test. At our working heights, 97–99% of positions
never reach a test.

**(c) Test the survivors until the walls appear.** Walk outward from
n₀ in both directions; the first surviving position that turns out to
be prime on each side is a **fence**. The distance between the left
and right fences *is* the gap, and it is **born verified**: every
interior position is either sieved-out (provably composite) or was
tested and failed.

**(d) Price it before you run it.** The number of independent attempts
(**windows** — distinct values of k) needed before both fences land
far enough out follows a measured exponential law. Knowing that law,
plus the measured speed of the hardware, converts any target on any
leaderboard into a number: **so many GPU-days.** Then a record hunt is
a purchase decision, not a lottery ticket.

## 3. The science (measured, gated, and with error bars)

The load-bearing results, each with its measurement provenance in
`docs/` and its code in this repo:

- **The fence-rate law (Buchstab).** The rate at which candidate
  fences turn out prime is **λ(u) = e^γ · ω(u)** per unit of merit,
  where ω is the Buchstab function and **u = ln(j)/ln(zd)** measures
  how far outside the "free" region you are. Confirmed three
  independent ways, including a 94,885-fence out-of-sample test with
  zero fitted parameters (χ² p = 0.19) and a preregistered forward
  prediction confirmed at 6–7σ in both directions. The classical
  Mertens-style rate is the u→∞ limit and misfits by up to 21× at
  high merit.
- **The unified cost law.** Put every leaderboard on one axis with
  **u(m, D) = 1 + ln(m/2)/ln(D·ln10)** (m = merit, D = decimal
  digits); then the exponential cost is **E(m, D) = m·σ(u)** with σ a
  two-parameter curve whose leading coefficient is
  **a = 1.8169 ± 0.0367 — equal to e^γ within 1.0σ** (26 calibration
  points, R² = 0.994; deriving this constant is the open theorem).
  Out-of-sample checks at three heights land within 0.3–2.6%.
- **The d-axis.** Dividing the primorial by small d relocates which
  positions each small prime can kill. Drop-2 (d = 2, k odd) doubles
  the free desert without surrendering the floor and halves the near
  fence rate to e^γ·ω(2) — measured 1.82× more merit per test.
  The construction is folklore among record holders; the *pricing*
  and the identification of the rate as a Buchstab value are, to our
  knowledge, new.
- **Survivor structure at extreme height.** At 26,599 digits with
  zd ≈ 61,000, every even survivor j in the working window must be
  2q or 4q for a prime q > zd — the candidates are forced
  almost-primes, and the survivor density (0.0167/unit, vs naive
  0.0407) follows from that structure exactly.
- **The staircase.** With the law calibrated, each +1 of merit costs
  ×2.4–2.6 in compute at fixed height, and the entire all-time merit
  table — from its entry bar to a fixed multiple past its nine-year
  crown — is priced in fleet-days by one configuration.
- **Dead ends, kept dead.** Candidate scoring: null at 14σ. Wing-
  weighted covering: net zero at production. Deeper sieving beyond
  the regime boundary: cost, not benefit. Every retired multiplier
  died against a finished control, and stays in the record.

## 4. The machine

One liturgy runs every campaign, at every height, on CPUs or GPUs:

```
design  ->  make  ->  drive  ->  fold  ->  ... (rings 2..R) ...  ->  finish
(rings)    (sieve)   (PRP)     (verdicts)                        (walk fences)
```

- **Design (`theater/*/ladder*.py`, `exchange/`).** Choose zd, d, k
  digits, and a ladder of **rings** — nested windows sized so each
  costs about the same expected number of fence-primes (E ≈ 1.7 per
  ring). A k that shows a prime in ring 1 is discarded immediately;
  survivors advance outward. The ladder concentrates testing on the
  ~e^-E fraction of ks that could possibly be records.
- **Make (`theater/raid610/scanhunt_v0.py` + `tools/fastmake.py`).**
  The sieve factory: for a block of ~8,300 ks, compute every ring
  survivor. Vectorized per-prime across the whole block;
  byte-identical (gated) to the reference per-k path.
- **Drive.** Fermat/PRP-test the candidates. On GPUs:
  `cuda/g1_fermat_v2.cu` — a Montgomery-arithmetic kernel with a
  **Gerbicz error check** on every test (zero alarms across 18.5M+
  verdicts); measured 516–523k tests/s/card at the 2048-bit class.
  On CPUs at extreme height: `tools/pfgw_drv.py` shards candidates
  across PFGW processes.
- **Fold.** Read the verdict file, count fence-primes per k, advance
  survivors to the next ring. Every file carries a magic number and a
  count; mismatches fail loudly. Fold statistics (E per ring) are the
  live health metric — the campaign certifies itself every block.
- **Finish / walk.** A k that clears the full ladder is a **finalist**:
  walk its true fences and record the gap. `tools/shard_walk.py` does
  the same for **salvage** — see below — and its sieve is proven
  correct by exact set-equivalence against an independent
  implementation.
- **Salvage (`tools/salvage_v0.py`, `tools/shard_walk.py`).** The
  campaign's exhaust is ore: a k killed at ring r still has a
  *certified prime-free core* out to ring r−1's edge, and often one
  fence far beyond. Walking discarded ks recovered, among others, a
  size-table crown and an all-time-merit entry — at seconds per k.
  Doctrine: sweeps touch only fossils (age-gated manifests), never a
  live theater's working files.
- **Verification chain.** (1) Sieved-out interior = provably
  composite. (2) Every tested candidate has a GEC-checked or
  PFGW-issued verdict. (3) Finds are independently re-proved
  (separate library, both endpoints) before banking. (4) The public
  record's notary re-proves endpoints and re-sieves the interior on
  independent hardware at submission. Nothing depends on trusting a
  single program.

- **September machinery (RC11/RC12).** A persistent **bucket sieve**
  (`tools/sieve/`, FK lattice walk, one 24-byte record per prime) and
  its GPU port (`cuda/gbs.cu`) sieve every window to 10¹⁰ — one card
  sieves for the whole box (`theater/raid610/gbsd.py`, the *sieve
  card*), byte-identical to the CPU reference (gates G-BSD, G-GBS,
  G-SV incl. stop-and-resume). A **full-window sparsity predictor**
  (residue tables for primes to 10⁵) ranks the pool before testing:
  ×1.42 crown-λ per tested window (gate G-PRED). A **ladder manager**
  (`ladder.py`, one process per card) replaced 700 shell loops,
  replay-gated identical (G-LADDER). Feeders and drivers pinned to
  reserved cores. `daily.sh` is the one-screen production read;
  `harvest_hourly.sh` walks every fossil and keeps the campaign ledger.

## 5. Campaigns and results

Three "theaters" ran this architecture at three heights (details,
configs, and preregistrations in `docs/` and `theater/`):

| theater | height | target board | outcome |
|---|---|---|---|
| raid610 | ~611 digits | all-time merit table | **the record: 59,724 @ merit 42.5192** (previous record 41.9388, 2017); **#2: 58,416 @ 41.5882**; 20 certified first-occurrence records in the list, ~25,000 further claims in the ledger |
| strike24k | ~6,152 digits | largest gap @ merit ≥ 30 | **crown**: 426,520 @ 30.1156 (+11 size records at merit 25–30) |
| mono | ~26,599 digits | largest gap @ merit ≥ 20 | **1,383,648 @ 22.59**, 1,348,726 @ 22.02, 1,263,196 @ 20.62 |

Plus the ≥2,500-digit merit crown (209,420 @ 33.638) and its guard
(201,646 @ 32.385) from the 2,704-digit campaign. The record and its
runner-up came out of the **salvage walk** over near-miss windows —
asymmetric gaps that a symmetric ring ladder discards — a channel the
cost law had not priced; the paper does. All entries were submitted
under `mvojvoda` on 2026-09-22 and re-verified by the list's own
server; endpoints of the certified batch are ECPP-proven (`records/`).
Every find above was **priced before it was hunted**, and the realized
costs sit inside the predicted bands — the cost ledger (hardware,
hours, dollars) is part of the release.

Throughput of record (September 2026, one 4×RTX 5090 box): 44–45k
windows/s sustained, ~64k crown-effective, with the CPU nearly idle.

## 6. Reproducibility

- **Preregistration.** Campaign configs, expected bands, and success
  criteria are written down (dated) before data collection;
  amendments are dated; verdicts (PASS / REFUTED) are filed strictly
  — including the refuted ones.
- **Gates.** No component touches a real pool before passing a
  known-answer corpus, a bit-exact comparison against an independent
  implementation, and a fault-injection drill. Gate scripts live in
  `gates/`; the rule "a green gate on code the gate does not cover is
  worse than no gate" is enforced culturally and in review.
- **Lineage.** `LINEAGE.md` maps every canonical tool to its source
  machine, SHA-256, and the gate that certified it.
- **Corrections ledger.** Mistakes are filed by name — including the
  AI assistant's — with mechanism and date. Several appear in the
  papers because the *pattern* (underpowered data reads as structure;
  controls must finish) is itself a result.
- **Find files.** Every find is reconstructible from one small text
  file (k, zd, d, fences); anyone with this repo can re-prove any
  claim end-to-end.

## 7. Repository map

```
tools/      canonical operational tools (sieve factory, drivers,
            walkers, salvage, submission formatter, notary client)
gates/      known-answer + equivalence + fault-injection gates
exchange/   the pricing instruments: pricer_v1 (cost law -> GPU-days),
            merit_price_v0 (bridge-exact certifier), fit_sigma_v1
            (the unified-law fit), audit + resonance tools
theater/    per-campaign configs and loops (raid610, mono, strike24k)
cuda/       GPU kernel sources (g1_fermat family, gbs.cu GPU sieve) + gate harness
tools/sieve/ the persistent bucket sieve (C): bsieve.c, bs_api.c, fk_walk.c + referees
records/    what is on the Prime Gap List: submission lines, the treasury by venue,
            record endpoints, verification chain (certificates ship with the data archive)
deploy/kit_v8/ the current kit as deployed (o1_kit v8.56; notes KIT_v8.5x_NOTE.md)
docs/       mission, preregistrations, cost calculus, novelty sweep,
            retrodictions, session handoffs
history/    frozen snapshots of earlier eras (arch2704 construction
            campaign; full deployed-tool archive) — cited, not run
LINEAGE.md  the tool provenance table
```

Not in this repo: the **vault** (find files, ledgers, campaign states,
raw manifests, databases) ships as a separate data archive with a DOI.

## 8. Running it

`deploy/kit_v8/` holds the current kit (o1_kit v8.56; KIT_v8.5x_NOTE.md describe each step since v8.54) - the machinery that set the records; `deploy/fresh_box.sh` stands it up (quick start below). `history/kit_v1_2026-08/` is the August kit, kept as history.

## 9. Standing on shoulders

The field already had gap *construction* in the folklore, excellent
sieves — notably **S. Troisi's combined_sieve
([arXiv:2012.03771](https://arxiv.org/abs/2012.03771))**, which
out-sieves ours and is cited with gratitude — numerical record-
probability tooling, and the /d trick at the top of the record list.
What we believe is new: the measured fence-rate law and its Buchstab
identification, the unified cost law with its e^γ coefficient, the
one-equation design grammar (zd ≈ 1.01·ln n₀), frontier audits of
existing records on their own artifacts, and a fully verified,
priced, reproducible pipeline. All novelty claims are phrased "to our
knowledge"; the audit numbers stand as measurements regardless.

## 10. Glossary — the mumbo-jumbo decoder

| term | meaning |
|---|---|
| **primorial, zd#** | product of all primes ≤ zd |
| **n₀** | the gap's center: k · zd#/d |
| **k** | the small free integer scanned; one k = one **window** |
| **d** | small divisor of zd# (the "d-axis" design dial) |
| **j** | offset from n₀; candidates are n₀ + j |
| **survivor** | a j with no factor ≤ Q (the sieve bound) |
| **fence** | first prime found on each side; the gap's endpoints |
| **merit** | gap / ln(p₁) |
| **ring / ladder** | nested windows; ks advance outward only while prime-free |
| **E** | expected fence-primes over a region; cost ≈ e^E windows |
| **β** | probability a survivor is prime ≈ e^γ·lnQ/ln n₀ |
| **fold** | verdict-ingestion step; produces per-ring statistics |
| **finalist** | a k that cleared the whole ladder |
| **salvage / crumb** | walking discarded ks' certified cores for gaps |
| **window rate** | windows/second; the campaign's speedometer |
| **GEC** | Gerbicz error check — per-test hardware-fault detection |
| **born verified** | interior composite-certified at find time |
| **claimcheck** | querying the public list + staging queue before submitting |
| **theater** | one campaign at one height (raid610 / mono / strike24k) |
| **bank / freeze / parade** | finds are stored, not submitted, until one coordinated release |

---

*BEACON is M. Vojvoda's campaign (records under the handle mvojvoda).

## Environment
Python 3.10+, numpy (gmpy2 for verification). GPU path: CUDA 12+
(kernel source in cuda/g1_fermat_v3.cu; built by deploy/fresh_box.sh). CPU-height path: PFGW
(sourceforge; expression syntax used throughout).
