# CROWN_CALC v1-RC5 (2026-08-23, 23:20 UTC) -- frozen on G-V2 (crown venue live)

Supersedes RC4 numerically; structure unchanged. G-K2 caveat (x1.05 on W_med) still open.

## Measured (crown venue, box1, kit v4.2, 60-min steady read)
- **27,550 w/s box = 2.381e9 windows/day**; per card 6,736-7,064 (avg 6,915); t/w **67.2**; ratio 0.562; 0 faults.
- Venue cost vs raid610 (29,293): -6.0%, within the observed run-to-run band; t/w unchanged (+0.3%).
- Ladder: rings 1568,4374,7244,10198,13500,17734,22818,31576; cap merit 45.0; G-L1/G-L2 both PASS
  (edges 1-6 reproduced raid610's exactly on an independent sieve; mint block byte-identical, cum-E in band).

## Crown economics at the frozen rate (W_med = 1.176e12 windows)
| plan | card-days (median) | 40 cards | 80 cards |
|---|---|---|---|
| Plan A today | 1,969 | 49 d | 25 d |
| Plan A + O4' + O3 [MODEL] | ~1,310 | 33 d | **16 d GO** |
| Plan C (#2-#6, m>=39.7) | ~364 | **9.1 d GO** | 4.6 d |
In 8 days on 40 cards: median best ~39.8; P(crown) ~11%; P(>=39.7 row) ~54%; E[>=38] ~3.3.

## Standing state
- Box1 hunts the crown venue since 2026-08-23 21:13 UTC; the crown (41.94) is inside the fence (cap 45).
- raid610 CLOSED with its best banked (52,868 @ 37.6945). Treasury and fossils untouched.
- Soak (R3) clock runs from the 21:13 relaunch; fleet rental gated on soak + R2 crontab + R5 freeze.
- Next builds: O4' schedule fit (offline, from ledger copies) -> O3 landing-enumeration C library
  (bitmap gate vs fastmake_c) -> CUDA pre-pass. Then the 80-card question is a purse question only.

## Appendix A (RC5.1 addendum, 2026-08-24): fleet card economics
Frozen numbers above unchanged. Card-days in this calculator are 5090 card-days (4.461e10 tests).
Conversion for other silicon, [MODEL] until each is gated by G1 A+D on a rented unit:
- RTX 4090 ~ 0.5 x 5090-card (sm_89 already in the binary).
- RTX 5060 Ti 16 GB ~ 0.28 x 5090-card (~3.5x slower; spec-ratio model), i.e. Plan C's ~364 5090-card-days
  ~ 1,300 5060Ti-card-days; at ~$0.09/h that is ~$2.8k vs ~$3.8k on 5090s -- cheaper in dollars, ~3.5x the
  slots and stand-ups. Same picture for Plan A. Verdict rule: dollars favor small cards only when listings
  supply enough slots; time and ops favor 5090s. The >=2,500-digit track is where small cards genuinely win.
