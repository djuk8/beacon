# Kit v8.55 - the October tune-up (2026-10-06)

Measured on the 8x RTX 5090 box (Xeon 8380, 160 threads): 72-77k -> 99.2k windows/s (12.7k per testing card, 11.3k per sieve card),
2.2x box1, every change gated (verdicts or outputs identical) before it went live. Built by tools/make_v855.py from kit v8.54 in place.

1. Driver: FERMAT_GEC (default 0) - the Gerbicz-Li check is gone: +13.0% tests/s (514,850 -> 581,795 on an idle 5090), verdicts
   byte-identical on 200 known primes + 200 composites and on 200k random candidates. Its job is now done by an hourly CANARY
   (every card re-runs those 400 known candidates; tools/canary, cron :43, /root/beacon/raid610/canary.log) and, as always, by the
   notary/ECPP/list server on every claim. Build -DFERMAT_GEC=1 for the G2 fault-injection drill.
2. Driver: DRIVER_SPIN (default 0) - cudaDeviceScheduleBlockingSync: the host thread sleeps while the GPU works instead of spinning
   a core (99% -> 11% of a core per driver, same tests/s). On the 8-card box that was ~32 cores.
3. Predictor v2 (bs_api.c pred_run): periodic table per prime + periodic add into an int32 accumulator; identical sums, x5.6 per
   pool on the daemons' real tables (daemon tails 2.5 s -> 0.65 s). go_crown builds bs_api.so with -march=native.
4. Harvest and daily read: hunt_s* (was hunt_s1*: fossils from ladder seeds >= 2000 were never walked - ~6% on 4-card boxes,
   ~25-36% on 8 cards; the Japan backlog of 26,951 was walked on 2026-10-06, best 36.26, no top-ten lost); the daily landing count
   also matches archived names; salvage_v1 archives already-walked duplicates too; a second harvest skips while a walk is running.
5. onstart: BSDNICE default 0 (rental containers cannot lower a nice value again).
6. fresh_box: the driver run-check fix, the seed files written before any step that can fail, the canary checked on card 0 before
   launch, and the canary cron next to the harvest cron.

Open after v8.55: DEEPR=2 (ring 2 deep-sieved to 1e8; ring 2 carries 28% of all GPU tests at Q=1e5) - A/B running on the Japan box;
slim manifests + numpy fold (~2-4 cores); the TPI sweep at 2048 bits; walking rung-5 fossils (~+5% at the record tier).
Rental rule learned: this pipeline wants ~16 CPU cores per 5090 for headroom (the Xeon 8380 box: 10 per card, now enough after 2-3).
