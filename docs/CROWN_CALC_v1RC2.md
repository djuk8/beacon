# CROWN_CALC v1-RC2  (2026-08-21)
PHYSICS UNCHANGED from v1-RC: E=28.16, W_med=1.176e12,
1,527 card-days post-O1, card-day=4.461e10 tests. This revision
ONLY re-cuts plans to the real fleet (5x 8-GPU = 40 cards) and
adds the two new gated levers. Numbers change only via gates.

## LEVER LADDER (each with mechanism + gate; nothing ungated ships)
O1  early-exit driver            x2.09   [gate: G-A0 corpus + shadow]
O3G deep sieve IN-KERNEL (GPU)   x1.51 @1e9 / x2.01 @1e12
    landings 1-5us vs PRP 112us; feed problem void; test
    vectors = S7/S8 unknowns files + T1 canary
                                          [gate: byte-match + canary]
O4  asymmetric completion (optimal stopping on exact rho(j))
    x1.0-1.4 -- EXACTLY COMPUTABLE, zero hardware
                                          [gate: the computation itself]
O5  swap-config sweep at 616     x1.05-1.2 [gate: box1 pilot fold-stat]

## PATHS TO 20 DAYS ON 40 CARDS (median)
alpha: O1 + O3G@1e12                     -> 19.0 d   ($6.8K med)
beta:  O1 + O3G@1e9 + (O4*O5 >= 1.27)    -> <=20 d
floor: O1 + O3G@1e9 only                 -> 25.3 d   (miss; hold fire
       or accept per Mario's call)
GO RULE: fire only if the FROZEN post-gate number <= ~20-22 d
on the contracted fleet. Otherwise: Plan C (decapitate top-5 on
40 cards: ~6 d median) or stand down. No middle mush.

## BUILD ORDER (Claude builds, Mario gates)
wk1: O1 driver (+pipelining hygiene) -> G-A0 gate on box1
wk1: O4 exact DP computation (zero-meter; prereg bands first)
wk2: O3-GPU pass in same driver -> byte-gate vs unknowns files,
     T1 canary at production mstart; depth 1e9 then 1e12 probe
wk2: O5 pilot config sweep (box1, one bay)
then: CROWN_CALC v1 FINAL = frozen product of GREEN gates only;
both signatures; hash; procurement (5x8 across >=3 landlords,
pilot + observed resurrection each); fire.
