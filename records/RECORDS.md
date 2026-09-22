# records/ -- what BEACON has put on the Prime Gap List (status 2026-09-22)

## Boards
| board | entry | status |
|---|---|---|
| **All-time merit record** | gap 59,724, merit **42.5192**, 17440361647223*1439#/2310-21464 (611 digits) | in list as C?D under `mvojvoda` (2026-09-22); ECPP certificates for both endpoints (C?C requested) |
| All-time merit #2 | gap 58,416, merit 41.5882, 17325055497313*1439#/2310-29514 | same |
| Largest gap with merit >= 30 | gap **426,520** @ 30.1156, 180020881*14341#/30030-158374 (6,151 digits) | server-verified 2026-09-22 (batch commit pending) |
| Largest gap with merit >= 20 | 1,383,648 @ 22.59; 1,348,726 @ 22.02; 1,263,196 @ 20.62 (61493#/30030, 26,599 digits) | submitted 2026-09-22, in verification |
| >= 2,500-digit class merit | 209,420 @ 33.638 (Crown 2) and 201,646 @ 32.385 (Crown 1, in list C?D 2026-09-22) | Crown 2 pending submission |
| First-occurrence (per gap size) | 20 certified (batch1_top20.txt, all in list); ~25,000 further claims in the campaign ledger | bulk submission being arranged |

## Files
- `submission_lines.txt`, `batch1_top20.txt` -- the Nicely-format lines (gap status merit year discoverer digits start-prime).
- `treasury_all.txt` -- the August finds by venue (zd d gap merit k jl jr source).
- `gap*_p1.dec/.in`, `gap*_p2.dec/.in` -- the four record endpoints (decimal, and Primo candidate format).
- `RECORD_README.md`, `BEACON_abstract.pdf` -- the record package notes and the one-page abstract.
- `arbitrage_map_v0.csv` -- the per-gap-size record table snapshot used for claim checking.
- ECPP certificates (CM 0.4.3 `ecpp`, PARI/GP `primecert` format; each verified with `primecertisvalid`) and notary certificates are in the data archive (`batch1_top20_certs.tgz`, Zenodo), not in this repo.

## Verification chain (every reported gap)
1. Reconstruction from the tuple (k, zd, d, jl, jr): `tools/notary_v2.py` rebuilds the primorial, the endpoints and every interior integer; interior proven composite (sieve factor to 1e9 or failed base-2 Fermat), endpoints PRP (6 strong bases + GMP), plus an independent GMP `next_prime` walk. Verdict VALID required.
2. Endpoints proven prime by ECPP (`ecpp -n N -f cert`), certificate verified independently with PARI/GP.
3. The Prime Gap List server re-verifies endpoints and interior on submission (`tools/claimcheck_v1.py` pre-checks a claim against the table; `tools/certify_batch.py` runs 1+2 over a whole batch).
