# BEACON record package -- 2026-09-22

## The finds (notary v2 VALID on box1; repeat on shredder for the independent-machine certificate)
| gap | merit | start prime (611 digits) | jl | jr | found | tier |
|---|---|---|---|---|---|---|
| **59,724** | **42.5192** | 17440361647223*1439#/2310-21464 | -21464 | +38260 | 2026-09-22 06:21Z | rung-6 fossil, salvage walk |
| 58,416 | 41.5882 | 17325055497313*1439#/2310-29514 | -29514 | +28902 | 2026-09-21 17:21Z | rung-6 fossil, salvage walk |
Current record merit (prime gap list): 41.9388 (gap 8350, 87 digits, 2017). 59,724 beats it; 58,416 would rank #2 all-time.

## What is proven and what is not (yet)
- Interior: EVERY integer between the endpoints is proven composite (sieve factor to 1e9, or failed base-2 Fermat) -- deterministic. Done (notary_cert_gap*.json).
- Endpoints: PRP only (6 strong bases + GMP is_prime(50) + independent next_prime walk). A record entry needs PROVEN primes -> ECPP.

## ECPP (do on shredder; both gaps' endpoints in parallel; ~1-3 h each at 611 digits)
Option A -- Primo (ellipsa.eu, Marcel Martin; Linux binary): candidate files gap*_p1.in / gap*_p2.in are in Primo's [Candidate] N= format.
  primo gap59724_p1.in   -> gap59724_p1.out (the certificate). Verify with Primo's built-in checker before packaging.
Option B -- CM / ecpp (Andreas Enge, https://www.multiprecision.org/cm/): ecpp -c -n $(cat gap59724_p1.dec) > gap59724_p1.cert ; ecpp --check gap59724_p1.cert
Both certificate formats are accepted by the prime gap list maintainers; Primo is the traditional one.

## Submission (after the certificates)
- Lines in submission_lines.txt (status C?P -> C once certified). Format: gap, status, merit, year, discoverer, digits, start-prime expression.
- Prime Gap List project (github.com/primegap-list-project) / the mersenneforum "Prime Gap Searches" thread; attach: notary_cert_gap59724.json, notary_cert_gap58416.json, the ECPP certificates, and the DOI of the method paper (Zenodo) if ready.
- Discoverer string: djuk8 (Mario) -- with the software credited as BEACON (ladder + salvage walk), notary v2.

## Provenance kept
~/RECORD on box1: ledger_lines.txt, the fossil manifests for both k, notary_cert_*.json. Copy the whole directory off the box.

## STATUS 2026-09-22 — COMPLETE (mathematics)
- Notary v2: VALID on box1 (both gaps); repeat on shredder for the second-machine certificate.
- ECPP: CM 0.4.3 `ecpp -c` certificates for all four endpoints (84-88 KB each), self-check true; independently verified with PARI/GP `primecertisvalid` = 1 for all four.
- Status in submission_lines.txt: C (certified) for both gaps.
- Package contents: notary_cert_gap59724.json, notary_cert_gap58416.json (x2 machines), gap*_p1.cert, gap*_p2.cert (4), gap*.dec (4), submission_lines.txt, the fossil manifests (box1 ~/RECORD), ledger_lines.txt.
- Remaining: Zenodo DOI of the method + arXiv (Mario's gate), then submission to the Prime Gap List project; the parade (23,319 per-gap-size claims) follows in batches.
