# Running BEACON yourself

This is the code that found the 2026 merit records (59,724 at merit 42.52, 59,302 at 42.09, and most of today's top 20). It is a research
pipeline, not a polished app: it was built on rented GPU containers, and it expects to run as root on Linux. If you are comfortable with
CUDA, gcc and a shell, you can have it hunting in an hour or two. It has run on boxes of 4 and 8 RTX 5090s; it supports a single GPU (the one
card sieves and tests), but nobody has run it that way yet, so the first single-GPU reports on the forum are welcome.

## What you need

- Linux with root, an NVIDIA GPU and its driver. A rented container (vast.ai, RunPod and the like) is the easiest start. Windows: try WSL2.
- Cards with 16 GB or more sieve to 1e10; smaller cards get 1e9 automatically (about a tenth slower).
- About 16 CPU cores per RTX 5090 for full speed, 32 GB RAM or more, a few GB free in /dev/shm.
- Prerequisites (Ubuntu): `apt install build-essential git pari-gp libgmp-dev`, a CUDA 12+ toolkit with `nvcc`,
  `python3 -m pip install numpy gmpy2`.

## Pick your k-range

Every machine needs its own range, or two people test the same numbers. Pick a seed N from 1 to 999: it owns k from 1e16 + N*1e15 for
1e15 (about a month of a single 5090). Post your seed in the forum thread before you start, and look there for the ones already taken.
k below 1e16 is the author's range.

## Start

    git clone https://github.com/djuk8/beacon ~/lab/beacon && cd ~/lab/beacon
    bash deploy/fresh_box.sh --seed N

`fresh_box.sh` builds the GPU Fermat driver for your card (NVlabs' CGBN is cloned on the way), checks it on known primes, builds the residue
cache (about 15 minutes) and the sieves, runs the identity gate (GPU sieve against an independent CPU sieve, byte for byte), and launches
the hunt with a watchdog cron that relaunches anything that dies. The defaults are the configuration that hunts today: one residue class of
k mod 2310 per sieve card (k = 317 mod 2310; with more than 4 cards a second sieve card takes 1993), rings 1 and 2 sieved on the GPU.
`--mixed` runs the older all-classes mode, `--kbase K` sets the start of the range yourself.

After 20 minutes:

    bash ~/beacon/p3/o1_kit/daily.sh

prints windows per second in four-hour slices, the harvest and the best gaps. Healthy: GPUs at 100%, about 12-14k windows/s per RTX 5090
(a 4090 a bit over half that). Expect, per 5090, one or two gaps of merit 36+ a day; merit 40+ is rarer, and the #1 spot is a matter of
months on one card.

## From finds to the Prime Gap List

Every walked gap lands in `~/beacon/raid610/campaign_ledger.log` (`gap merit k jl jr ...`). To see which ones improve the list:

    git clone --depth 1 https://github.com/primegap-list-project/prime-gap-list pgl
    python3 tools/claims_live.py ~/beacon/raid610/campaign_ledger.log pgl/allgaps.sql --min-merit 30
    awk '{split($3,a,"*"); print a[1], $2}' claims.txt > ks.txt && python3 tools/rewalk.py ks.txt

`claims.txt` holds lines like `59302 42.0914 1223553299725363*1439#/2310-37096` (gap, merit, start prime); `rewalk.py` re-derives each gap
from its k alone and flags any mismatch. Paste the lines into the submission form at primegaps.cloudygo.com with your own short handle as
discoverer; the server re-verifies every gap before it enters the list. For a top-20 merit, certify the endpoints with ECPP
(`tools/certify_batch.py`) and post the certificates.

## When something is off

- `fresh_box: FAIL: ...` names the missing piece; fix it and run the same command again.
- The knobs are plain files in `~/beacon/raid610` (`*.txt`); `/root/onstart_raid_v2.sh` reads them on every start.
- The notes `KIT_v8.5x_NOTE.md` describe each change and how it was gated; `README.md` explains the method.
- Questions and results: the mersenneforum Prime Gap Searches subforum.
