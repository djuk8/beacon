# The 300-digit venue (kit v8.53, 2026-09-25)

A venue is now a file: ~/beacon/raid610/VENUE.json (absent = the crown, 1439#/2310, 611 digits, 2048-bit class). venue.py reads it for
ladder_crown.py (edge design), prewarm_cache.py (residue cache names), ladder.py (manager config), onstart (the sieve daemon's --zd --bits --rings)
and go_crown (the G-L2 mint gate and the ladder file). Kit v8.53 = v8.52 + venue.py + venue300.json + the four readers + the 1024-bit class in g1_fermat_v3.cu
(measured 1.90M tests/s vs 486k at 2048 on an idle 5090; TPI 8, LTPB 256, window 5).

venue300.json: zd 683, d 2310 (swap 2 3 5 7 11), kdig 13 -> n0 ~ 10^306 (1017 bits), 1024-bit class, merit-45 window (edges designed at that height, ~+-15,700).

Stand-up on a NEW box (keep the 611 hunt where it is):
    git clone <repo> ~/lab/beacon && cd ~/lab/beacon && bash deploy/fresh_box.sh --venue 300 --seed 5000
fresh_box copies venue300.json to VENUE.json, designs ladder_v300.json (ladder_crown.py edges, a minute), builds the driver with the 1024 class,
then go_crown builds the residue cache for zd 683, runs the make-identity gate and G-L2 at the new venue, and launches with the daemon on
--zd 683 --bits 1024 --rings <designed edges>. The gate is the acceptance: G-L2 PASS at the venue or nothing launches.
Seeds for this venue start at 5000 (k0 = 1e12 + 8e9*5000 = 4.1e13): its own k-range, disjoint from the 611 boxes.

What to read after launch: daily.sh (expect a much higher w/s than 611 - the class is 3.9x faster and windows are half the tests - and
pass1 near the same 0.215); the first walked gaps land at sizes 20-27k (merit 30-39 at ln n0 ~ 705). Every one is a claim at a size the
611 campaign never reaches. The ledger's tier counts per box-day at this height are the companion paper's out-of-sample figure.

Untested until the first 300 box: the edge design at zd 683 (sanity: edges should scale as ln n0, ~0.50 of the crown's: 1568 -> ~790,
31576 -> ~15,850), the predictor tables for the new wheel (built automatically by gbsd, keyed by zd), and the sieve at 1e10 on a smaller wheel.
Report the first failure line; each is a venue defect, not a box problem.
